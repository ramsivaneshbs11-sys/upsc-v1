"""
app/retrieval/sibling_expansion.py
────────────────────────────────────
Production-grade Bidirectional Sibling Chunk Expansion.

PROBLEM SOLVED
──────────────
When the chunker splits a dense PDF page into sub-chunks (e.g. a table header
lands in chk_0026 and the table rows land in chk_0025), vector search may only
retrieve the header chunk — making the LLM unable to answer the full question.

SOLUTION
────────
For every retrieved chunk N, we expand BOTH directions in a configurable window:

    Radius = 2 → fetches [N-2, N-1, N, N+1, N+2]

This guarantees that:
  ✅  Headers always arrive with their following table/list rows.
  ✅  Numbered lists always arrive with their preceding label.
  ✅  Long administrative tables (e.g. Ashta Pradhan ministers) are never split.

SCORE DECAY
───────────
Sibling chunks inherit the matched chunk's score but are penalised by a
per-hop decay factor so the LLM/reranker still prioritises the exact match:

    hop-1 score = original_score × (1 - SIBLING_SCORE_DECAY)^1
    hop-2 score = original_score × (1 - SIBLING_SCORE_DECAY)^2

CONFIGURATION  (app/core/config.py or .env)
────────────────────────────────────────────
    SIBLING_EXPANSION_RADIUS  = 2    # chunks to expand each side (default 2)
    SIBLING_SCORE_DECAY       = 0.15 # fractional score penalty per hop (default 0.15)

Public API:
    expand_with_siblings(chunks, preprocessed_dir, radius, score_decay) -> list[dict]
"""

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import SIBLING_EXPANSION_RADIUS, SIBLING_SCORE_DECAY

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_preprocessed_chunks(file_name: str, preprocessed_dir: Path) -> dict[str, dict]:
    """
    Load all chunks from a preprocessed JSON file, indexed by chunk_id.

    Args:
        file_name:        The PDF filename from chunk metadata (e.g. 'abc123.pdf').
        preprocessed_dir: Path to the data/preprocessed/ directory.

    Returns:
        Dict mapping chunk_id -> chunk dict, or empty dict if the file is missing.
    """
    stem = Path(file_name).stem                    # strip .pdf
    stem = stem.replace("_preprocessed", "")       # safety guard against double suffix
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


def _parse_chunk_num(chunk_id: str) -> tuple[str, int] | None:
    """
    Parse a chunk_id like 'chk_0026' into ('chk', 26).

    Returns:
        (prefix, number) tuple, or None if the format is unexpected.
    """
    try:
        prefix, num_str = chunk_id.rsplit("_", 1)
        return prefix, int(num_str)
    except (ValueError, AttributeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def expand_with_siblings(
    chunks: list[dict[str, Any]],
    preprocessed_dir: Path,
    radius: int = SIBLING_EXPANSION_RADIUS,
    score_decay: float = SIBLING_SCORE_DECAY,
) -> list[dict[str, Any]]:
    """
    Bidirectional sibling chunk expansion.

    For every retrieved chunk N, fetches chunks [N-radius … N-1] and
    [N+1 … N+radius] from the same document, de-duplicates, and appends
    them to the context with a decayed relevance score.

    Args:
        chunks:           List of reranked chunk dicts (output of reranker).
        preprocessed_dir: Path to the data/preprocessed/ directory.
        radius:           Number of chunks to expand in each direction (default: config).
        score_decay:      Fractional score penalty per hop away from the anchor (default: config).

    Returns:
        Augmented list with sibling chunks appended (deduplicated, ordered by hop distance).

    Example (radius=2):
        Retrieved: chk_0026
        Expanded:  chk_0024 (hop-2, score×0.72), chk_0025 (hop-1, score×0.85),
                   chk_0026 (anchor), chk_0027 (hop-1, score×0.85), chk_0028 (hop-2, score×0.72)
    """
    if not chunks or radius <= 0:
        return chunks

    # Track already-present (file_name, chunk_id) pairs to avoid duplicates
    existing_keys: set[tuple[str, str]] = {
        (c.get("metadata", {}).get("file_name", ""), c["chunk_id"])
        for c in chunks
    }
    additions: list[dict[str, Any]] = []

    # One preprocessed JSON is loaded per file_name per request (in-memory cache)
    file_cache: dict[str, dict[str, dict]] = {}

    for chunk in chunks:
        metadata  = chunk.get("metadata", {})
        file_name = metadata.get("file_name", "")

        # Skip chunks without a valid file reference
        if not file_name:
            continue

        parsed = _parse_chunk_num(chunk["chunk_id"])
        if parsed is None:
            logger.debug(f"[SiblingExpand] Cannot parse chunk_id: {chunk['chunk_id']}")
            continue

        prefix, anchor_num = parsed
        base_score       = chunk.get("score", 0.0)
        base_rerank      = chunk.get("rerank_score", 0.0)

        # Load the preprocessed document once per file per request
        if file_name not in file_cache:
            file_cache[file_name] = _load_preprocessed_chunks(file_name, preprocessed_dir)
        all_doc_chunks = file_cache[file_name]

        # Build offsets: [-2, -1, +1, +2] for radius=2 (negative = before, positive = after)
        offsets = list(range(-radius, 0)) + list(range(1, radius + 1))

        for offset in offsets:
            target_num = anchor_num + offset
            if target_num < 1:
                continue  # chunk numbers start at 1

            sibling_id  = f"{prefix}_{target_num:04d}"
            sibling_key = (file_name, sibling_id)

            if sibling_key in existing_keys:
                logger.debug(
                    f"[SiblingExpand] {sibling_id} already present — skipping."
                )
                continue

            sibling = all_doc_chunks.get(sibling_id)
            if sibling is None:
                # Chunk does not exist (e.g. we are at the document boundary)
                logger.debug(
                    f"[SiblingExpand] {sibling_id} not found in '{file_name}' — boundary reached."
                )
                continue

            # Score decay: further siblings score lower so LLM keeps correct ranking
            hop          = abs(offset)
            decay_factor = (1.0 - score_decay) ** hop
            sibling_chunk: dict[str, Any] = {
                "chunk_id":     sibling_id,
                "text":         sibling.get("text", ""),
                "score":        round(base_score  * decay_factor, 6),
                "rerank_score": round(base_rerank * decay_factor, 6),
                "metadata":     sibling.get("metadata", {}),
                "source":       chunk.get("source", "qdrant"),
                "collection":   chunk.get("collection", ""),
                "file_id":      chunk.get("file_id"),
                "_sibling_of":  chunk["chunk_id"],
                "_sibling_hop": offset,          # +ve = after anchor, -ve = before
            }
            additions.append(sibling_chunk)
            existing_keys.add(sibling_key)

            logger.info(
                f"[SiblingExpand] Injected {sibling_id} "
                f"(hop {offset:+d}, score×{decay_factor:.2f}) "
                f"← anchor: {chunk['chunk_id']} | file: '{file_name}'"
            )

    if additions:
        logger.info(
            f"[SiblingExpand] ✅ Radius={radius} | Decay={score_decay} | "
            f"Added {len(additions)} sibling chunk(s) across "
            f"{len(file_cache)} document(s)."
        )

    return chunks + additions
