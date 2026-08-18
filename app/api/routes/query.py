"""
app/api/routes/query.py
────────────────────────
POST /api/v1/query — Full RAG pipeline with Anti-Hallucination.

Pipeline per request:
  1. Classify query      (Gemini Flash → class + confidence)
  2. Route by confidence:
       High (>0.80)       → Filter 1 Qdrant collection → Vector Search
       Medium (0.50–0.80) → Top-2 Qdrant collections  → Merged Vector Search
       Low (<0.50)        → DuckDuckGo Global Retrieval
  3. Rerank candidates   (cross-encoder MiniLM)
  4. Anti-Hallucination  (3 layers):
       Layer 1 — Score Gate: block LLM if best rerank_score < 0.0
       Layer 2 — Strict context-only prompt: LLM must not use outside knowledge
       Layer 3 — Citation enforcement: every fact tagged with [chunk_id]
  5. Return grounded answer + cited chunks

Request body:
    {
        "query":  "What is cultural ecology?",
        "top_k":  5   (optional, default 5)
    }

Response:
    {
        "query":             "What is cultural ecology?",
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
        "chunks":            [ { ... } ]
    }
"""

import logging
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.retrieval.query_classifier import classify_query
from app.retrieval.retrieval_router import route_and_retrieve
from app.retrieval.generator        import generate_grounded_answer
from app.core.config                import RETRIEVAL_FINAL_TOP_K

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


class QueryResponse(BaseModel):
    # ── Query metadata ─────────────────────────────────────────────────────────────────────────
    query:            str
    classification:   str
    confidence:       float
    all_scores:       dict
    routing:          str
    total_candidates: int
    # ── Anti-hallucination generation output ───────────────────────────────────────────
    answer:           str           # Grounded answer (or "insufficient info")
    answered:         bool          # False = LLM couldn't answer from context
    citations:        list[str]     # Raw chunk_ids cited inline in the answer
    rich_citations:   list[CitationResult]  # Human-readable: doc name + page + preview
    gated:            bool          # True = score gate blocked LLM
    gate_reason:      Optional[str] # Why gate triggered (or None)
    # ── Retrieved evidence ───────────────────────────────────────────────────────────────────────
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
async def query_knowledge_base(body: QueryRequest) -> QueryResponse:
    """
    Full RAG pipeline:
    Query → Classify → Route (High/Medium/Low) → Vector/Web Search
         → Rerank → Score Gate → Strict LLM → Grounded Answer + Citations
    """
    query = body.query.strip()
    top_k = body.top_k or RETRIEVAL_FINAL_TOP_K

    logger.info(f"[QUERY] Incoming: '{query[:80]}' | top_k={top_k}")

    # ── Step 1: Classify ───────────────────────────────────────────────────────
    try:
        classifier_result = classify_query(query)
    except Exception as exc:
        logger.exception(f"[QUERY] Classification failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Query classification failed: {exc}",
        )

    # ── Step 2 + 3: Route → Search → Rerank ───────────────────────────────────
    try:
        retrieval_result = route_and_retrieve(
            query=query,
            classifier_result=classifier_result,
            top_k=top_k,
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

    # ── Step 4: Anti-Hallucination Generation ─────────────────────────────────
    # Layer 1: Score gate (inside generator)
    # Layer 2: Strict context-only prompt
    # Layer 3: Citation enforcement
    try:
        generation = generate_grounded_answer(
            query=query,
            chunks=chunks,
            source=routing,
        )
    except Exception as exc:
        logger.exception(f"[QUERY] Generation failed: {exc}")
        # Fail gracefully — return chunks without answer rather than crash
        generation = {
            "answer":      "Answer generation temporarily unavailable.",
            "answered":    False,
            "citations":   [],
            "gated":       True,
            "gate_reason": f"Generation error: {exc}",
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

    logger.info(
        f"[QUERY] Complete — class='{classifier_result['classification']}', "
        f"conf={classifier_result['confidence']:.2f}, routing='{routing}', "
        f"answered={generation['answered']}, gated={generation['gated']}, "
        f"candidates={len(candidates)}, chunks={len(chunk_results)}"
    )

    return QueryResponse(
        query=            query,
        classification=   classifier_result["classification"],
        confidence=       classifier_result["confidence"],
        all_scores=       classifier_result.get("all_scores", {}),
        routing=          routing,
        total_candidates= len(candidates),
        answer=           generation["answer"],
        answered=         generation["answered"],
        citations=        generation["citations"],
        rich_citations=   [
            CitationResult(**c) for c in generation.get("rich_citations", [])
        ],
        gated=            generation["gated"],
        gate_reason=      generation.get("gate_reason"),
        chunks=           chunk_results,
    )
