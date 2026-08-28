"""
app/retrieval/sibling_expansion.py
────────────────────────────────────
Post-retrieval sibling chunk expansion.

When the chunker splits a dense page into sub-chunks (sub_chunk_index / total_sub_chunks),
semantically relevant content can end up in the *next* sibling chunk — invisible to the
reranker because it didn't match the query's embedding as strongly.

This module inspects each retrieved chunk's metadata and, where the next consecutive
sibling exists in the preprocessed JSON, appends it to the context so the LLM sees
the complete passage.

Example:
    chk_0023  -> sub_chunk_index=1, total_sub_chunks=4  -> loads chk_0024 automatically
    chk_0024  -> sub_chunk_index=2, total_sub_chunks=4  -> already present (deduped)

Public API:
    expand_with_siblings(chunks, preprocessed_dir) -> list[dict]
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_preprocessed_chunks(file_name: str, preprocessed_dir: Path) -> dict[str, dict]:
    """
    Load all chunks from a preprocessed JSON file indexed by chunk_id.

    Args:
        file_name:        The PDF filename from chunk metadata (e.g. 'abc123.pdf').
        preprocessed_dir: Path to the data/preprocessed/ directory.

    Returns:
        Dict mapping chunk_id to chunk dict, or empty dict if file not found.
    """
    stem = Path(file_name).stem                        # strip .pdf
    stem = stem.replace("_preprocessed", "")           # safety guard
    preprocessed_path = preprocessed_dir / f"{stem}_preprocessed.json"

    if not preprocessed_path.exists():
        logger.debug(f"[SiblingExpand] Preprocessed file not found: {preprocessed_path}")
        return {}

    try:
        with open(preprocessed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = data.get("chunks", [])
        return {c["chunk_id"]: c for c in chunks}
    except Exception as exc:
        logger.warning(f"[SiblingExpand] Failed to load {preprocessed_path}: {exc}")
        return {}


def expand_with_siblings(
    chunks: list[dict[str, Any]],
    preprocessed_dir: Path,
) -> list[dict[str, Any]]:
    """
    Expand retrieved chunks by appending their next consecutive sibling sub-chunk
    from the same preprocessed document, if that sibling is not already in the list.

    Only expands chunks that have sub_chunk_index AND total_sub_chunks metadata,
    meaning they are part of a split dense page. The sibling chunk is appended
    at the end (deduped) and inherits the parent chunk's score.

    Args:
        chunks:           List of reranked chunk dicts (output of reranker).
        preprocessed_dir: Path to the data/preprocessed/ directory.

    Returns:
        Augmented list with sibling chunks appended at the end (deduplicated).
    """
    if not chunks:
        return chunks

    existing_keys: set[tuple[str, str]] = {(c.get("metadata", {}).get("file_name", ""), c["chunk_id"]) for c in chunks}
    additions: list[dict[str, Any]] = []

    # Cache opened preprocessed files to avoid repeated disk reads per request
    file_cache: dict[str, dict[str, dict]] = {}

    for chunk in chunks:
        metadata  = chunk.get("metadata", {})
        sub_idx   = metadata.get("sub_chunk_index")
        total_sub = metadata.get("total_sub_chunks")
        file_name = metadata.get("file_name", "")

        # Only expand split-page chunks that are not the last sub-chunk
        if sub_idx is None or total_sub is None or not file_name:
            continue


        # Derive sibling chunk_id by incrementing the numeric suffix by 1
        # e.g. "chk_0023" -> "chk_0024"
        try:
            current_id   = chunk["chunk_id"]
            prefix, num  = current_id.rsplit("_", 1)
            sibling_id   = f"{prefix}_{int(num) + 1:04d}"
        except (ValueError, AttributeError):
            logger.debug(f"[SiblingExpand] Cannot derive sibling ID from: {chunk['chunk_id']}")
            continue

        sibling_key = (file_name, sibling_id)
        if sibling_key in existing_keys:
            logger.debug(f"[SiblingExpand] Sibling {sibling_id} for {file_name} already in result set — skipping.")
            continue

        # Load the preprocessed file (use cache)
        if file_name not in file_cache:
            file_cache[file_name] = _load_preprocessed_chunks(file_name, preprocessed_dir)
        all_doc_chunks = file_cache[file_name]

        sibling = all_doc_chunks.get(sibling_id)
        if sibling is None:
            logger.debug(f"[SiblingExpand] Sibling {sibling_id} not found in '{file_name}'")
            continue

        # Build a retrieval-compatible dict for the sibling chunk
        sibling_chunk: dict[str, Any] = {
            "chunk_id":    sibling_id,
            "text":        sibling.get("text", ""),
            "score":       chunk.get("score", 0.0),
            "rerank_score": chunk.get("rerank_score", 0.0),
            "metadata":    sibling.get("metadata", {}),
            "source":      chunk.get("source", "qdrant"),
            "collection":  chunk.get("collection", ""),
            "file_id":     chunk.get("file_id"),
            "_sibling_of": current_id,
        }
        additions.append(sibling_chunk)
        existing_keys.add(sibling_key)

        logger.info(
            f"[SiblingExpand] Injected sibling {sibling_id} "
            f"(sub {sub_idx + 1}/{total_sub}) alongside {current_id} "
            f"from '{file_name}'"
        )

    if additions:
        logger.info(f"[SiblingExpand] Added {len(additions)} sibling chunk(s) to context.")

    return chunks + additions
