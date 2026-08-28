"""
app/retrieval/retrieval_router.py
──────────────────────────────────
Confidence-based retrieval router.

Routes the retrieval strategy based on the classifier confidence score:

    High   (> 0.80) → Filter to 1 collection  → Vector Search
    Medium (0.50–0.80) → Search Top-2 collections → Merge Results
    Low    (< 0.50)  → Global Retrieval (DuckDuckGo web search)

All paths feed into the cross-encoder Reranker → Top-K chunks.

Public API:
    route_and_retrieve(query, classifier_result, top_k) -> dict
"""

import logging
from typing import Any

from app.core.config import (
    QDRANT_COLLECTION_MAP,
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_FINAL_TOP_K,
    PREPROCESSED_DIR,
)
from app.retrieval.vector_search    import search_collections
from app.retrieval.search_pipeline  import parallel_search
from app.retrieval.reranker         import rerank
from app.retrieval.sibling_expansion import expand_with_siblings

logger = logging.getLogger(__name__)


def _top_n_collections(all_scores: dict[str, float], n: int) -> list[str]:
    """
    Return the Qdrant collection names for the top-N scoring classes.

    Args:
        all_scores: {class_name: confidence_score} dict from the classifier.
        n:          Number of top classes to pick.

    Returns:
        List of Qdrant collection name strings (from QDRANT_COLLECTION_MAP).
        Skips any class that has no mapped collection.
    """
    sorted_classes = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    collections    = []
    for cls, _ in sorted_classes[:n]:
        col = QDRANT_COLLECTION_MAP.get(cls)
        if col:
            collections.append(col)
    return collections


def route_and_retrieve(
    query:             str,
    classifier_result: dict[str, Any],
    top_k:             int | None = None,
    mode:              str = "prelims",
) -> dict[str, Any]:
    """
    Route the query to the correct retrieval strategy and return reranked chunks.

    Args:
        query:             The user's original query text.
        classifier_result: Output of query_classifier.classify_query().
        top_k:             Final number of chunks to return (default: RETRIEVAL_FINAL_TOP_K).
        mode:              Prompt mode passed through to the generator
                           ("prelims" | "mains" | "current_affairs").

    Returns:
        dict with:
            routing    (str)       — "high_confidence" / "medium_confidence" / "low_confidence"
            candidates (list[dict])— raw candidates before reranking
            chunks     (list[dict])— top-K reranked chunks
            mode       (str)       — prompt mode forwarded from caller
    """
    # ── Dynamic mode-specific top_k ──────────────────────────────────────────
    # Prelims  → 5 chunks  (sharp factual precision, fastest)
    # Current Affairs → 8 chunks  (multi-source web coverage)
    # Mains    → 10 chunks (broad analytical context for multi-dimensional answers)
    if top_k is None:
        if mode == "mains":
            top_k = 10
        elif mode == "current_affairs":
            top_k = 8
        else:  # prelims (default)
            top_k = RETRIEVAL_FINAL_TOP_K

    # ── Current Affairs Mode: Bypass Classifier → Direct Web Search ───────────
    # Local Qdrant collections only contain static textbook PDFs (History /
    # Anthropology). They cannot answer questions about recent events.
    # When mode="current_affairs", skip confidence routing entirely and go
    # straight to the parallel web search pipeline.
    if mode == "current_affairs":
        logger.info(
            f"Router: mode='current_affairs' → Bypassing classifier. "
            f"Forcing parallel web search (DuckDuckGo + SearXNG)."
        )
        candidates = parallel_search(user_query=query)
        top_chunks  = rerank(query=query, candidates=candidates, top_k=top_k)
        # Web search chunks don't have sub_chunk_index so expand_with_siblings is a no-op here.
        # Included for consistency in case future web-cached chunks adopt the same metadata.
        top_chunks = expand_with_siblings(top_chunks, PREPROCESSED_DIR)
        logger.info(
            f"Router: [current_affairs] candidates={len(candidates)}, "
            f"top_k={len(top_chunks)}"
        )
        return {
            "routing":    "current_affairs_web",
            "candidates": candidates,
            "chunks":     top_chunks,
            "mode":       mode,
        }

    confidence  = classifier_result["confidence"]
    all_scores  = classifier_result.get("all_scores", {})
    top_class   = classifier_result["classification"]

    # ── Route: High Confidence ─────────────────────────────────────────────────
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        routing     = "high_confidence"
        collections = _top_n_collections(all_scores, n=1)

        logger.info(
            f"Router: HIGH confidence ({confidence:.2f}) → "
            f"Single collection: {collections}"
        )

        candidates = search_collections(
            query=query,
            collection_names=collections,
            top_k=RETRIEVAL_CANDIDATE_K,
        )


    # ── Route: Medium Confidence ───────────────────────────────────────────────
    elif confidence >= LOW_CONFIDENCE_THRESHOLD:
        routing     = "medium_confidence"
        collections = _top_n_collections(all_scores, n=2)

        logger.info(
            f"Router: MEDIUM confidence ({confidence:.2f}) → "
            f"Top-2 collections: {collections}"
        )

        candidates = search_collections(
            query=query,
            collection_names=collections,
            top_k=RETRIEVAL_CANDIDATE_K,
        )

    # ── Route: Low Confidence — Parallel Web Search (DDG + SearXNG) ────────────
    else:
        routing = "low_confidence"

        logger.info(
            f"Router: LOW confidence ({confidence:.2f}) → "
            f"Parallel web search (DuckDuckGo + SearXNG)"
        )

        candidates = parallel_search(user_query=query)

    # ── Rerank candidates → Top-K ──────────────────────────────────────────────
    top_chunks = rerank(
        query=query,
        candidates=candidates,
        top_k=top_k,
    )

    # ── Sibling Expansion: inject next consecutive sub-chunk if split ───────────
    # Guarantees complete lists/sections reach the LLM when a dense page was
    # split across sub-chunks during ingestion. No re-ingestion required.
    top_chunks = expand_with_siblings(top_chunks, PREPROCESSED_DIR)

    logger.info(
        f"Router: Retrieval complete — routing='{routing}', "
        f"candidates={len(candidates)}, top_k={len(top_chunks)}, mode='{mode}'"
    )

    return {
        "routing":    routing,
        "candidates": candidates,
        "chunks":     top_chunks,
        "mode":       mode,
    }
