"""
app/retrieval/vector_search.py
───────────────────────────────
Embeds the user query using the same BAAI/bge-base-en-v1.5 model used during
ingestion, then performs a Qdrant similarity search against one or more
collections and returns candidate chunks.

Public API:
    search_collections(query, collection_names, top_k) -> list[dict]
"""

import logging
from typing import Any

from app.services.qdrant_service import get_qdrant_client
from app.services.embedding_service import _get_model as get_embedding_model

logger = logging.getLogger(__name__)


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string using the BGE model.
    Uses the same singleton model already loaded by embedding_service.

    Returns:
        list[float] — 768-dimensional normalized embedding vector.
    """
    model = get_embedding_model()
    vector = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    return vector[0].tolist()


def search_collections(
    query: str,
    collection_names: list[str],
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """
    Perform vector similarity search across one or more Qdrant collections.

    Args:
        query:            The user's query text.
        collection_names: List of Qdrant collection names to search.
        top_k:            Number of candidate results to return per collection.

    Returns:
        List of candidate chunk dicts, sorted by score (descending), deduplicated
        across collections. Each dict has:
            {
                "chunk_id":  str,
                "text":      str,
                "score":     float,
                "metadata":  dict,
                "source":    "qdrant",
                "collection": str,
            }
    """
    if not collection_names:
        logger.warning("search_collections called with empty collection_names list.")
        return []

    query_vector = embed_query(query)
    client       = get_qdrant_client()

    all_results: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for collection_name in collection_names:
        try:
            if hasattr(client, "query_points"):
                response = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=top_k,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                )

            for hit in hits:
                payload   = hit.payload or {}
                chunk_id  = payload.get("chunk_id", str(hit.id))

                # Deduplicate across collections
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)

                all_results.append({
                    "chunk_id":   chunk_id,
                    "text":       payload.get("text", ""),
                    "score":      round(float(hit.score), 6),
                    "metadata":   payload.get("metadata", {}),
                    "file_id":    payload.get("file_id"),
                    "source":     "qdrant",
                    "collection": collection_name,
                })

            logger.info(
                f"VectorSearch: '{collection_name}' returned {len(hits)} hits."
            )

        except Exception as exc:
            logger.error(
                f"VectorSearch: Error searching '{collection_name}': {exc}"
            )

    # Sort merged results by score descending
    all_results.sort(key=lambda x: x["score"], reverse=True)
    logger.info(
        f"VectorSearch: {len(all_results)} total candidates across "
        f"{len(collection_names)} collection(s)."
    )
    return all_results
