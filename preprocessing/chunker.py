"""
chunker.py
────────────
Page-Wise Hybrid text chunker.

Strategy:
  1. Group all cleaned blocks by their page number.
  2. Process pages in order, maintaining a carry-forward buffer for tiny pages.
  3. MIN-SIZE MERGE : If a page's total text < min_page_size chars (default 300),
     carry its blocks forward and merge them with the next page.
  4. MAX-SIZE SPLIT : If the accumulated page text > max_chunk_size chars (default 1200),
     split into sub-chunks at BLOCK BOUNDARIES (never mid-block).
  5. All chunks receive exact page_numbers metadata (a small list, usually one page).
  6. No character overlap — page boundaries make overlap unnecessary.
"""

import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger("chunker")

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_MAX_CHUNK_SIZE = 1200
DEFAULT_MIN_PAGE_SIZE  = 300


def create_chunks(
    clean_data: Dict[str, Any],
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_page_size: int  = DEFAULT_MIN_PAGE_SIZE,
    # Legacy parameter accepted but ignored (overlap is not used in page-wise mode)
    overlap: int = 0,
) -> Dict[str, Any]:
    """
    Creates page-wise hybrid chunks from a cleaned document structure.

    Args:
        clean_data:     Dict containing cleaned content blocks and metadata.
        max_chunk_size: Hard character cap per chunk (default 1200).
                        Keeps chunks safely under BGE's 512-token limit.
        min_page_size:  Minimum page character count before merging with the
                        next page (default 300).  Avoids weak single-heading
                        embeddings.
        overlap:        Accepted for CLI backward-compatibility; ignored in
                        page-wise mode.

    Returns:
        Dict containing chunk list and summary metadata.
    """
    blocks   = clean_data.get("blocks", [])
    doc_meta = clean_data.get("metadata", {})
    file_name = doc_meta.get("file_name", "unknown")

    # ── Step 1: Group blocks by page number ───────────────────────────────────
    pages: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        pages[block.get("page_num", 1)].append(block)

    sorted_page_nums = sorted(pages.keys())
    total_pages      = len(sorted_page_nums)

    # ── Step 2: Iterate pages and apply hybrid logic ──────────────────────────
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 1

    # Carry-forward state (for tiny pages that get merged into the next)
    carry_blocks:        List[Dict[str, Any]] = []
    carry_page_nums:     List[int]            = []
    carry_mermaid_codes: List[str]            = []

    for idx, page_num in enumerate(sorted_page_nums):
        page_blocks = pages[page_num]
        is_last_page = (idx == total_pages - 1)

        # Combine carry-forward + this page
        all_blocks    = carry_blocks + page_blocks
        all_page_nums = carry_page_nums + [page_num]

        # Calculate total text length for this combined set
        total_chars = sum(len(b.get("text", "").strip()) for b in all_blocks)

        # ── MIN-SIZE MERGE ────────────────────────────────────────────────────
        # If this page is too small AND it's not the very last page,
        # carry its content forward to merge with the next page.
        if total_chars < min_page_size and not is_last_page:
            carry_blocks        = all_blocks
            carry_page_nums     = all_page_nums
            carry_mermaid_codes = _collect_mermaid(all_blocks)
            logger.debug(
                f"Chunker: Page {page_num} tiny ({total_chars} chars) — "
                f"carrying forward to merge with page {sorted_page_nums[idx + 1]}."
            )
            continue

        # Page (+ any carry) is ready to be committed.
        # Reset carry state.
        carry_blocks        = []
        carry_page_nums     = []
        carry_mermaid_codes = []

        # ── MAX-SIZE SPLIT ────────────────────────────────────────────────────
        if total_chars <= max_chunk_size:
            # Single chunk: whole page fits within the size cap.
            text       = " ".join(b.get("text", "").strip() for b in all_blocks if b.get("text", "").strip())
            block_ids  = [b.get("block_id", "") for b in all_blocks]
            mer_codes  = _collect_mermaid(all_blocks)

            chunks.append(_build_chunk_dict(
                chunk_id      = f"chk_{chunk_counter:04d}",
                text          = text.strip(),
                page_nums     = sorted(set(all_page_nums)),
                block_ids     = block_ids,
                file_name     = file_name,
                mermaid_codes = mer_codes,
            ))
            chunk_counter += 1

        else:
            # Dense page: split at block boundaries into sub-chunks.
            sub_chunks = _split_into_sub_chunks(all_blocks, max_chunk_size)
            total_subs = len(sub_chunks)

            for sub_idx, sub in enumerate(sub_chunks, start=1):
                chunks.append(_build_chunk_dict(
                    chunk_id         = f"chk_{chunk_counter:04d}",
                    text             = sub["text"],
                    page_nums        = sorted(set(all_page_nums)),
                    block_ids        = sub["block_ids"],
                    file_name        = file_name,
                    mermaid_codes    = sub["mermaid_codes"],
                    sub_chunk_index  = sub_idx,
                    total_sub_chunks = total_subs,
                ))
                chunk_counter += 1

            logger.debug(
                f"Chunker: Page {page_num} dense ({total_chars} chars) — "
                f"split into {total_subs} sub-chunks."
            )

    logger.info(f"Chunker: Created {len(chunks)} page-wise hybrid chunks for '{file_name}'")

    return {
        "metadata":    doc_meta,
        "chunk_count": len(chunks),
        "chunks":      chunks,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_into_sub_chunks(
    blocks: List[Dict[str, Any]],
    max_chunk_size: int
) -> List[Dict[str, Any]]:
    """
    Split a list of blocks into sub-chunks, each ≤ max_chunk_size characters.
    Splits only at block boundaries where possible.
    If a single block itself exceeds max_chunk_size, it is split at word
    boundaries to guarantee no chunk escapes the safety cap.
    """
    sub_chunks   = []
    current_text = ""
    current_ids  = []
    current_mer  = []

    for block in blocks:
        text     = block.get("text", "").strip()
        block_id = block.get("block_id", "")
        mer_code = block.get("mermaid_code")

        if not text:
            continue

        # If this single block already exceeds the cap, word-split it first.
        if len(text) > max_chunk_size:
            # Flush any accumulated text as a sub-chunk first
            if current_text:
                sub_chunks.append({
                    "text":          current_text.strip(),
                    "block_ids":     current_ids,
                    "mermaid_codes": current_mer if current_mer else None,
                })
                current_text = ""
                current_ids  = []
                current_mer  = []

            # Word-boundary split the oversized block
            words     = text.split()
            word_buf  = ""
            for word in words:
                candidate = (word_buf + " " + word).strip() if word_buf else word
                if len(candidate) > max_chunk_size and word_buf:
                    sub_chunks.append({
                        "text":          word_buf.strip(),
                        "block_ids":     [block_id],
                        "mermaid_codes": [mer_code] if mer_code else None,
                    })
                    word_buf = word
                else:
                    word_buf = candidate
            if word_buf:
                sub_chunks.append({
                    "text":          word_buf.strip(),
                    "block_ids":     [block_id],
                    "mermaid_codes": [mer_code] if mer_code else None,
                })
            continue

        # Normal block: check if adding it would exceed the cap
        would_exceed = current_text and (len(current_text) + 1 + len(text) > max_chunk_size)

        if would_exceed:
            # Commit current sub-chunk
            sub_chunks.append({
                "text":          current_text.strip(),
                "block_ids":     current_ids,
                "mermaid_codes": current_mer if current_mer else None,
            })
            current_text = text
            current_ids  = [block_id]
            current_mer  = [mer_code] if mer_code else []
        else:
            current_text = (current_text + " " + text).strip() if current_text else text
            current_ids.append(block_id)
            if mer_code:
                current_mer.append(mer_code)

    # Commit the final remaining sub-chunk
    if current_text:
        sub_chunks.append({
            "text":          current_text.strip(),
            "block_ids":     current_ids,
            "mermaid_codes": current_mer if current_mer else None,
        })

    return sub_chunks


def _collect_mermaid(blocks: List[Dict[str, Any]]) -> Optional[List[str]]:
    """Collect all mermaid_code values from a list of blocks."""
    codes = [b["mermaid_code"] for b in blocks if b.get("mermaid_code")]
    return codes if codes else None


def _build_chunk_dict(
    chunk_id:         str,
    text:             str,
    page_nums:        List[int],
    block_ids:        List[str],
    file_name:        str,
    mermaid_codes:    Optional[List[str]] = None,
    sub_chunk_index:  Optional[int]       = None,
    total_sub_chunks: Optional[int]       = None,
) -> Dict[str, Any]:
    """Build a standardised chunk dictionary."""
    metadata: Dict[str, Any] = {
        "file_name":        file_name,
        "page_numbers":     page_nums,
        "source_block_ids": block_ids,
    }
    if mermaid_codes:
        metadata["mermaid_codes"] = mermaid_codes
    if sub_chunk_index is not None:
        metadata["sub_chunk_index"]  = sub_chunk_index
        metadata["total_sub_chunks"] = total_sub_chunks

    return {
        "chunk_id":        chunk_id,
        "text":            text,
        "character_count": len(text),
        "metadata":        metadata,
    }
