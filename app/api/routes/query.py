"""
app/api/routes/query.py
────────────────────────
POST /api/v1/query — Full RAG pipeline with Anti-Hallucination.

Pipeline per request:
  1. Classify query      (Gemini Flash → class + confidence)
  2. Route by confidence:
       High (>0.80)       → Filter 1 Qdrant collection → Vector Search
       Medium (0.50–0.80) → Top-2 Qdrant collections  → Merged Vector Search
       Low (<0.50)        → Parallel Web Search (DuckDuckGo + SearXNG)
  3. Rerank candidates   (cross-encoder MiniLM)
  4. Anti-Hallucination  (3 layers):
       Layer 1 — Score Gate: block LLM if best rerank_score < 0.0
       Layer 2 — Mode-specific prompt (prelims/mains/current_affairs)
       Layer 3 — Citation enforcement: every fact tagged with [chunk_id]
  5. Return grounded answer + cited chunks

Request body:
    {
        "query":  "What is cultural ecology?",
        "top_k":  5,                    (optional, default 5)
        "mode":   "prelims"             (optional: prelims | mains | current_affairs)
    }

Response:
    {
        "query":             "What is cultural ecology?",
        "mode":              "prelims",
        "classification":    "Anthropology",
        "confidence":        0.92,
        "all_scores":        {"Anthropology": 0.92, "History": 0.08},
        "routing":           "high_confidence",
        "total_candidates":  20,
        "answer":            "Cultural ecology is... [chk_0012]",
        "answered":          true,
        "citations":         ["chk_0012"],
        "gated":             false,
        "gate_reason":       null,
        "log_info":          "...",
        "chunks":            [ { ... } ]
    }
"""

import logging
import asyncio
import json
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.retrieval.query_classifier import classify_query
from app.retrieval.retrieval_router import route_and_retrieve
from app.retrieval.generator        import (
    generate_grounded_answer,
    get_session_history,
    save_chat_message,
    format_history_for_prompt,
    condense_query,
)
from app.retrieval.response_cache   import get_response, set_response, clear_cache, cache_stats
from app.core.config                import RETRIEVAL_FINAL_TOP_K, TRUSTED_SITES, RESPONSE_CACHE_ENABLED
from app.database.session           import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The user's UPSC-related search query.",
        examples=["What is cultural ecology?"],
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Number of final chunks to return after reranking. "
            f"Default: {RETRIEVAL_FINAL_TOP_K}"
        ),
    )
    mode: str = Field(
        default="prelims",
        description=(
            "Prompt mode controlling answer style. "
            "'prelims' — MCQ/fact answer engine. "
            "'mains' — Structured analytical Mains answer. "
            "'current_affairs' — Temporally-grounded current events analysis."
        ),
        examples=["prelims", "mains", "current_affairs"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID to enable sliding-window chat conversation memory."
    )


class ChunkResult(BaseModel):
    chunk_id:     str
    text:         str
    score:        float
    rerank_score: float
    source:       str
    metadata:     dict


class CitationResult(BaseModel):
    chunk_id:  str
    document:  str
    pages:     Any             # int, list[int], or "?"
    preview:   str
    url:       Optional[str] = None


class QueryResponse(BaseModel):
    # ── Query metadata ──────────────────────────────────────────────────────────
    query:            str
    mode:             str           # Prompt mode used (prelims/mains/current_affairs)
    classification:   str
    confidence:       float
    all_scores:       dict
    routing:          str
    total_candidates: int
    # ── Anti-hallucination generation output ────────────────────────────────────
    answer:           str           # Grounded answer (or "insufficient info")
    answered:         bool          # False = LLM couldn't answer from context
    citations:        list[str]     # Raw chunk_ids cited inline in the answer
    rich_citations:   list[CitationResult]  # Human-readable: doc name + page + preview
    gated:            bool          # True = score gate blocked LLM
    gate_reason:      Optional[str] # Why gate triggered (or None)
    # ── Cache metadata ──────────────────────────────────────────────────────────
    cache_hit:        bool          # True = answer served from response cache
    # ── User-facing transparency log ────────────────────────────────────────────
    log_info:         str           # Human-readable confirmation of which DB was searched
    # ── Retrieved evidence ──────────────────────────────────────────────────────
    chunks:           list[ChunkResult]


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the UPSC RAG knowledge base (Anti-Hallucination)",
    description=(
        "Full RAG pipeline with 3-layer hallucination prevention:\n\n"
        "1. **Score Gate** — Blocks LLM if retrieved chunks have low relevance scores\n"
        "2. **Strict Context-Only Prompt** — LLM must answer ONLY from retrieved passages\n"
        "3. **Citation Enforcement** — Every claim tagged with source [chunk_id]\n\n"
        "Returns `answered: false` when the question is outside the knowledge base "
        "instead of hallucinating."
    ),
)
async def query_knowledge_base(
    body: QueryRequest,
    db: Session = Depends(get_db)
) -> QueryResponse:
    """
    Full RAG pipeline:
    Query → Classify → Route (High/Medium/Low) → Vector/Web Search
         → Rerank → Score Gate → Strict LLM → Grounded Answer + Citations
    """
    query = body.query.strip()
    top_k = body.top_k or RETRIEVAL_FINAL_TOP_K
    mode  = body.mode.strip().lower().replace(" ", "_").replace("-", "_") or "prelims"
    session_id = body.session_id

    logger.info(f"[QUERY] Incoming: '{query[:80]}' | top_k={top_k} | mode={mode} | session_id={session_id}")

    # ── Response Cache Lookup (skip for current_affairs and active chat sessions) ──
    # We skip cache when a session has history because the condensed query may differ
    # from the raw query, and multi-turn context changes the expected answer.
    use_cache = RESPONSE_CACHE_ENABLED and mode != "current_affairs" and not session_id
    if use_cache:
        cached = get_response(query, mode)
        if cached is not None:
            cached["cache_hit"] = True
            logger.info(f"[QUERY] Cache HIT — returning stored answer instantly.")
            return QueryResponse(**cached)

    # ── Load Conversation History & Condense Query ─────────────────────────────
    history_str = "No previous conversation history."
    search_query = query

    if session_id:
        # Load last 10 messages (5 turns) Chronologically
        history_msgs = await asyncio.to_thread(get_session_history, db, session_id, limit=10)
        history_str = format_history_for_prompt(history_msgs)
        # Rewrite query to be standalone if history exists
        search_query = await asyncio.to_thread(condense_query, query, history_str)

    # ── Step 1: Classify (using condensed search_query) ────────────────────────
    try:
        classifier_result = classify_query(search_query)
    except Exception as exc:
        logger.exception(f"[QUERY] Classification failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Query classification failed: {exc}",
        )

    # ── Step 2 + 3: Route → Search → Rerank ────────────────────────────────────
    try:
        retrieval_result = await asyncio.to_thread(
            route_and_retrieve,
            search_query,
            classifier_result,
            top_k,
            mode,
        )
    except Exception as exc:
        logger.exception(f"[QUERY] Retrieval/reranking failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Retrieval failed: {exc}",
        )

    chunks     = retrieval_result["chunks"]
    candidates = retrieval_result["candidates"]
    routing    = retrieval_result["routing"]

    # ── Step 4: Anti-Hallucination Generation ──────────────────────────────────
    try:
        generation = await asyncio.to_thread(
            generate_grounded_answer,
            query,
            chunks,
            routing,
            mode,
            history_str,
        )
    except Exception as exc:
        logger.exception(f"[QUERY] Generation failed: {exc}")
        # Fail gracefully — return chunks without answer rather than crash
        generation = {
            "answer":      "Answer generation temporarily unavailable.",
            "answered":    False,
            "citations":   [],
            "rich_citations": [],
            "gated":       True,
            "gate_reason": f"Generation error: {exc}",
            "mode":        mode,
        }

    # ── Build response ─────────────────────────────────────────────────────────
    chunk_results = [
        ChunkResult(
            chunk_id=     c.get("chunk_id", ""),
            text=         c.get("text", ""),
            score=        float(c.get("score", 0.0)),
            rerank_score= float(c.get("rerank_score", 0.0)),
            source=       c.get("source", "unknown"),
            metadata=     c.get("metadata", {}),
        )
        for c in chunks
    ]

    # ── Build user-facing log_info message ────────────────────────────────────
    classification  = classifier_result["classification"]
    confidence_pct  = classifier_result["confidence"] * 100
    citation_count  = len(generation["citations"])
    candidate_count = len(candidates)

    if routing == "high_confidence":
        log_info = (
            f"Query routed strictly to {classification} Database "
            f"({confidence_pct:.1f}% confidence). "
            f"{candidate_count} candidate chunks retrieved and reranked. "
            f"Answer backed by {citation_count} source(s). "
            f"No other database was searched."
        )
    elif routing == "medium_confidence":
        log_info = (
            f"Medium confidence ({confidence_pct:.1f}%) — Both History and Anthropology "
            f"databases were searched and merged. "
            f"{candidate_count} total candidates reranked. "
            f"Answer backed by {citation_count} source(s)."
        )
    elif routing == "low_confidence":
        log_info = (
            f"Low confidence ({confidence_pct:.1f}%) — Query did not match local databases. "
            f"Routed to parallel web search (DuckDuckGo + SearXNG + Bing). "
            f"{candidate_count} web results retrieved and reranked."
        )
    elif routing == "current_affairs_web":
        trusted_sources_str = ", ".join(TRUSTED_SITES)
        log_info = (
            f"Current Affairs mode — Local databases bypassed entirely. "
            f"Live web search performed via DuckDuckGo + SearXNG + Bing "
            f"(trusted sources: {trusted_sources_str}). "
            f"{candidate_count} web articles scraped and reranked. "
            f"Answer backed by {citation_count} source(s)."
        )

    else:
        log_info = (
            f"Routing: {routing} | Confidence: {confidence_pct:.1f}% | "
            f"Candidates: {candidate_count} | Citations: {citation_count}"
        )

    # Append gate/answer status to log_info
    if generation["gated"]:
        log_info += f" [GATED: {generation.get('gate_reason', 'Low relevance score')}]"
    elif not generation["answered"]:
        log_info += " [Result: Insufficient information in knowledge base.]"
    else:
        log_info += " [Result: Answer successfully generated.]"

    logger.info(
        f"[QUERY] Complete — class='{classification}', mode='{mode}', "
        f"conf={classifier_result['confidence']:.2f}, routing='{routing}', "
        f"answered={generation['answered']}, gated={generation['gated']}, "
        f"candidates={len(candidates)}, chunks={len(chunk_results)}"
    )
    logger.info(f"[LOG_INFO] {log_info}")

    result_payload = QueryResponse(
        query=            query,
        mode=             generation.get("mode", mode),
        classification=   classification,
        confidence=       classifier_result["confidence"],
        all_scores=       classifier_result.get("all_scores", {}),
        routing=          routing,
        total_candidates= candidate_count,
        answer=           generation.get("answer", ""),
        answered=         generation.get("answered", False),
        citations=        generation.get("citations", []),
        rich_citations=   generation.get("rich_citations", []),
        gated=            generation.get("gated", False),
        gate_reason=      generation.get("gate_reason"),
        cache_hit=        False,
        log_info=         log_info,
        chunks=           chunk_results,
    )

    # ── Save Conversation Turns to Database ────────────────────────────────────
    if session_id:
        # Save user query
        await asyncio.to_thread(save_chat_message, db, session_id, "user", query)
        # Save assistant answer (serialize response payload)
        response_json = json.dumps({
            "answer": result_payload.answer,
            "answered": result_payload.answered,
            "citations": result_payload.citations
        })
        await asyncio.to_thread(save_chat_message, db, session_id, "assistant", response_json)

    # ── Store in response cache (only when answered=True and no active session) ──
    if use_cache:
        set_response(query, mode, result_payload.model_dump())

    return result_payload


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.delete(
    "/cache",
    status_code=200,
    summary="Clear the response cache (admin)",
    description="Deletes all cached RAG responses. Subsequent requests will re-run the full pipeline.",
    tags=["admin"],
)
async def clear_response_cache():
    """
    Wipe all entries from the response cache.
    The next identical query will re-run classify → search → rerank → LLM.
    """
    deleted = await asyncio.to_thread(clear_cache)
    logger.info(f"[ADMIN] Response cache cleared — {deleted} entries removed.")
    return {"message": f"Response cache cleared. {deleted} entries removed."}


@router.get(
    "/cache/stats",
    status_code=200,
    summary="Response cache statistics (admin)",
    tags=["admin"],
)
async def response_cache_stats():
    """Return current response cache statistics (live entries, expired, config)."""
    stats = await asyncio.to_thread(cache_stats)
    return stats
