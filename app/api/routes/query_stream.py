"""
app/api/routes/query_stream.py
──────────────────────────────
POST /api/v1/query/stream — Server-Sent Events (SSE) streaming RAG pipeline.

Streams pipeline progress events to the client in real-time so the UI can
show "Searching…", "Analysing articles…", "Generating answer…" stages instead
of a blank loading screen.

Event format (text/event-stream):
    data: {"type": "progress", "stage": "searching",   "message": "🔍 Searching trusted sources..."}
    data: {"type": "progress", "stage": "scraping",    "message": "📄 Analysing 6 articles..."}
    data: {"type": "progress", "stage": "reranking",   "message": "⚡ Ranking relevant chunks..."}
    data: {"type": "progress", "stage": "generating",  "message": "✍️ Generating grounded answer..."}
    data: {"type": "result",   "payload": { ...full QueryResponse dict... }}
    data: {"type": "done"}
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.retrieval.query_classifier     import classify_query
from app.retrieval.retrieval_router     import route_and_retrieve
from app.retrieval.generator            import (
    generate_grounded_answer,
    get_session_history,
    save_chat_message,
    format_history_for_prompt,
    condense_query,
)
from app.retrieval.response_cache       import get_response, set_response
from app.core.config                    import RETRIEVAL_FINAL_TOP_K, TRUSTED_SITES, RESPONSE_CACHE_ENABLED
from app.database.session               import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query-stream"])


# ── Request schema (same as QueryRequest) ─────────────────────────────────────

class StreamQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    mode: str = Field(default="prelims")
    session_id: Optional[str] = Field(default=None)


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


def _progress(stage: str, message: str) -> str:
    return _sse({"type": "progress", "stage": stage, "message": message})


# ── Streaming generator ───────────────────────────────────────────────────────

async def _stream_pipeline(
    query: str,
    top_k: Optional[int],
    mode: str,
    session_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> AsyncGenerator[str, None]:
    """
    Run the full RAG pipeline and yield SSE events at each stage boundary.
    All blocking calls (search, rerank, LLM) are offloaded to asyncio.to_thread
    so the event loop is never blocked and SSE events are delivered immediately.
    """

    # ── Cache Fast-Path (skip for current_affairs and active sessions) ────────────
    # A cache hit instantly emits one progress + result + done event in <1ms
    # instead of running the full 4-stage pipeline.
    use_cache = RESPONSE_CACHE_ENABLED and mode != "current_affairs" and not session_id
    if use_cache:
        cached = await asyncio.to_thread(get_response, query, mode)
        if cached is not None:
            cached["cache_hit"] = True
            logger.info(f"[STREAM] Cache HIT — short-circuiting pipeline for: '{query[:60]}'")
            yield _progress("cache", "⚡ Serving answer from cache instantly...")
            yield _sse({"type": "result", "payload": cached})
            yield _sse({"type": "done"})
            return

    # ── Stage 0: Load History & Condense Query ────────────────────────────────
    yield _progress("classifying", "🔍 Loading conversation history and condensing query...")
    history_str = "No previous conversation history."
    search_query = query

    if session_id and db is not None:
        history_msgs = await asyncio.to_thread(get_session_history, db, session_id, limit=10)
        history_str = format_history_for_prompt(history_msgs)
        search_query = await asyncio.to_thread(condense_query, query, history_str)

    # ── Stage 1: Classify ──────────────────────────────────────────────────────
    yield _progress("classifying", "🔍 Classifying your query...")
    try:
        classifier_result = await asyncio.to_thread(classify_query, search_query)
    except Exception as exc:
        yield _sse({"type": "error", "message": f"Classification failed: {exc}"})
        return

    # ── Stage 2: Search ────────────────────────────────────────────────────────
    yield _progress("searching", "🌐 Searching trusted sources across the web...")

    # We run retrieval in a thread; but we want to emit "scraping" mid-way.
    # We achieve this by emitting the scraping event just before retrieval
    # returns (retrieval itself handles search+scrape internally).
    # A secondary delayed emit gives the user visible progress during scraping.
    async def _emit_scraping_after_delay():
        await asyncio.sleep(3.5)          # ~time for search providers to respond
        return _progress("scraping", "📄 Analysing articles from PIB, The Hindu, Wikipedia...")

    scraping_task = asyncio.create_task(_emit_scraping_after_delay())

    # Run the heavy retrieval pipeline in a thread pool
    retrieval_task = asyncio.to_thread(
        route_and_retrieve,
        search_query,
        classifier_result,
        top_k,
        mode,
    )

    retrieval_result, scraping_msg = await asyncio.gather(
        retrieval_task,
        scraping_task,
        return_exceptions=True,
    )

    # Emit scraping message if retrieval hadn't already finished by then
    if isinstance(scraping_msg, str):
        yield scraping_msg

    if isinstance(retrieval_result, Exception):
        yield _sse({"type": "error", "message": f"Retrieval failed: {retrieval_result}"})
        return

    chunks     = retrieval_result["chunks"]
    candidates = retrieval_result["candidates"]
    routing    = retrieval_result["routing"]

    # ── Stage 3: Reranking done (already part of retrieval) ───────────────────
    yield _progress("reranking", f"⚡ Ranked {len(chunks)} relevant chunks...")

    # ── Stage 4: Generate ──────────────────────────────────────────────────────
    yield _progress("generating", "✍️ Generating grounded answer...")
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
        logger.exception(f"[STREAM] Generation failed: {exc}")
        generation = {
            "answer":        "Answer generation temporarily unavailable.",
            "answered":      False,
            "citations":     [],
            "rich_citations": [],
            "gated":         True,
            "gate_reason":   f"Generation error: {exc}",
            "mode":          mode,
        }

    # ── Build final result payload ─────────────────────────────────────────────
    classification  = classifier_result.get("classification", "unknown")
    confidence      = classifier_result.get("confidence", 0.0)
    confidence_pct  = confidence * 100
    citation_count  = len(generation.get("citations", []))
    candidate_count = len(candidates)

    if routing == "current_affairs_web":
        trusted_sources_str = ", ".join(TRUSTED_SITES[:5]) + "..."
        log_info = (
            f"Current Affairs mode — Live web search via DuckDuckGo + SearXNG + Bing "
            f"(trusted: {trusted_sources_str}). "
            f"{candidate_count} articles scraped and reranked. "
            f"Answer backed by {citation_count} source(s)."
        )
    elif routing == "high_confidence":
        log_info = (
            f"Routed to {classification} Database ({confidence_pct:.1f}% confidence). "
            f"{candidate_count} candidates reranked. "
            f"Answer backed by {citation_count} source(s)."
        )
    else:
        log_info = (
            f"Routing: {routing} | Confidence: {confidence_pct:.1f}% | "
            f"Candidates: {candidate_count} | Citations: {citation_count}"
        )

    if generation.get("gated"):
        log_info += f" [GATED: {generation.get('gate_reason', 'Low relevance score')}]"
    elif not generation.get("answered"):
        log_info += " [Result: Insufficient information in knowledge base.]"
    else:
        log_info += " [Result: Answer successfully generated.]"

    result_payload = {
        "query":            query,
        "mode":             generation.get("mode", mode),
        "classification":   classification,
        "confidence":       confidence,
        "all_scores":       classifier_result.get("all_scores", {}),
        "routing":          routing,
        "total_candidates": candidate_count,
        "answer":           generation.get("answer", ""),
        "answered":         generation.get("answered", False),
        "citations":        generation.get("citations", []),
        "rich_citations":   generation.get("rich_citations", []),
        "gated":            generation.get("gated", False),
        "gate_reason":      generation.get("gate_reason"),
        "cache_hit":        False,
        "log_info":         log_info,
        "chunks": [
            {
                "chunk_id":     c.get("chunk_id", ""),
                "text":         c.get("text", ""),
                "score":        float(c.get("score", 0.0)),
                "rerank_score": float(c.get("rerank_score", 0.0)),
                "source":       c.get("source", "unknown"),
                "metadata":     c.get("metadata", {}),
            }
            for c in chunks
        ],
    }

    yield _sse({"type": "result", "payload": result_payload})

    # ── Save Conversation Turns to Database ────────────────────────────────────
    if session_id and db is not None:
        await asyncio.to_thread(save_chat_message, db, session_id, "user", query)
        response_json = json.dumps({
            "answer": result_payload["answer"],
            "answered": result_payload["answered"],
            "citations": result_payload["citations"]
        })
        await asyncio.to_thread(save_chat_message, db, session_id, "assistant", response_json)

    # ── Write to response cache (only on success, no session, not current_affairs) ─
    if use_cache:
        await asyncio.to_thread(set_response, query, mode, result_payload)

    yield _sse({"type": "done"})
    logger.info(
        f"[STREAM] Complete — mode={mode}, routing={routing}, "
        f"answered={generation.get('answered')}, chunks={len(chunks)}"
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/query/stream",
    summary="Streaming RAG query with real-time progress events (SSE)",
    description=(
        "Same as `/api/v1/query` but streams Server-Sent Events (SSE) at each "
        "pipeline stage so the UI can show live progress instead of a blank screen.\n\n"
        "Event types:\n"
        "- `progress` — stage label + human-readable message\n"
        "- `result`   — full answer payload (same schema as QueryResponse)\n"
        "- `error`    — pipeline error message\n"
        "- `done`     — stream complete signal"
    ),
    response_class=StreamingResponse,
)
async def stream_query(
    body: StreamQueryRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    query = body.query.strip()
    top_k = body.top_k
    mode  = body.mode.strip().lower().replace(" ", "_").replace("-", "_") or "prelims"
    session_id = body.session_id

    logger.info(f"[STREAM] Incoming: '{query[:80]}' | top_k={top_k} | mode={mode} | session_id={session_id}")

    return StreamingResponse(
        _stream_pipeline(query, top_k, mode, session_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",      # Disable nginx buffering for SSE
            "Connection":     "keep-alive",
        },
    )
