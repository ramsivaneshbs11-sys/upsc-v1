"""
app/retrieval/reranker.py
──────────────────────────
Second-stage cross-encoder reranker using:
    cross-encoder/ms-marco-MiniLM-L-6-v2

Takes a user query and a list of candidate chunks (from vector search or web
search), scores each chunk against the query, and returns the top-K highest
scored chunks.

Public API:
    rerank(query, candidates, top_k) -> list[dict]
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Cross-encoder model singleton ─────────────────────────────────────────────
_reranker_model = None


def _get_reranker():
    """Lazy-load the cross-encoder model once per process."""
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder
        from app.core.config import RERANKER_MODEL_NAME

        logger.info(f"Loading cross-encoder reranker: {RERANKER_MODEL_NAME} …")
        _reranker_model = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)
        logger.info("Reranker model loaded ✓")
    return _reranker_model


def preload_reranker() -> None:
    """
    Eagerly initialise the cross-encoder model at server startup.

    Call this inside the FastAPI lifespan handler so the model is warm and
    ready before the first user request arrives, eliminating cold-start delay.
    """
    _get_reranker()
    logger.info("Reranker pre-loaded and ready ✓")


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Rerank candidate chunks using a cross-encoder model and return top-K.

    Args:
        query:      The user's original query string.
        candidates: List of candidate dicts from vector_search or web_search.
                    Each must have at least a "text" key.
        top_k:      Number of top chunks to return after reranking.

    Returns:
        List of top-K chunk dicts, each enriched with a "rerank_score" field,
        sorted by rerank_score descending.
    """
    if not candidates:
        logger.warning("Reranker called with empty candidate list.")
        return []

    try:
        reranker = _get_reranker()

        # Build (query, passage) pairs for the cross-encoder
        pairs = [(query, c["text"]) for c in candidates]

        # Predict relevance scores — higher is more relevant
        scores = reranker.predict(pairs, show_progress_bar=False)

        # Attach scores to candidates
        scored = []
        for chunk, score in zip(candidates, scores):
            scored.append({**chunk, "rerank_score": round(float(score), 6)})

        # Sort by rerank_score descending, take top-K
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        top_chunks = scored[:top_k]

        logger.info(
            f"Reranker: {len(candidates)} candidates → top {len(top_chunks)} selected. "
            f"Best score: {top_chunks[0]['rerank_score'] if top_chunks else 'N/A'}"
        )

        return top_chunks

    except Exception as exc:
        logger.error(f"Reranker failed: {exc} — returning top-{top_k} by vector score.")
        # Graceful fallback: return top-K by original vector/search score
        fallback = sorted(candidates, key=lambda x: x.get("score", 0.0), reverse=True)
        for chunk in fallback:
            chunk["rerank_score"] = chunk.get("score", 0.0)
        return fallback[:top_k]
