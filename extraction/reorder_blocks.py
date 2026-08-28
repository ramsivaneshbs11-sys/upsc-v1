"""
reorder_blocks.py
─────────────────
Fix 1: Column-aware reading order for multi-column PDF pages.

Problem
-------
On double-column pages Docling orders blocks purely by raw y-coordinate across
the whole page, causing left-column and right-column content to interleave and
the narrative to become incoherent.

Fix strategy
------------
Post-process ``text_blocks`` per page, before saving JSON:

1. Detect the page midpoint (defaults to ``page_width / 2``).
2. Split non-full-width blocks into left (``bbox[0] < mid_x - margin``) and
   right (``bbox[0] >= mid_x - margin``) columns.
3. Sort each column top→bottom.
   In Docling's coordinate system (0,0) is TOP-LEFT and y INCREASES downward,
   so top→bottom order corresponds to *ascending* ``bbox[1]``.
4. Concatenate: all of left column then all of right column.
5. Full-width blocks (bbox width > 70 % of page width) act as **section-break
   anchors** — they stay in their natural vertical position and the column sort
   only applies to non-full-width blocks between consecutive anchors.
6. Single-column pages fall through naturally: ``right_col`` will be empty and
   the page is returned in plain top→bottom order.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("reorder_blocks")


# ── 0. COLUMN MIDPOINT AUTO-DETECTION ─────────────────────────────────────────

def _detect_column_midpoint(
    blocks: List[Dict[str, Any]],
    page_width: float,
) -> float:
    """
    Auto-detects the horizontal midpoint that separates a 2-column page by
    finding the largest gap between distinct ``bbox[0]`` (left-edge) values
    within the middle 30 %–70 % horizontal band of the page.

    Rationale
    ---------
    Using ``page_width / 2`` as the split point fails when the column gutter is
    off-centre (common in textbooks with sidebar boxes or asymmetric margins).
    The largest x0 gap in the middle band is a robust proxy for the white-space
    channel between the two columns.

    Falls back to ``page_width / 2`` when:
    - Fewer than 4 non-full-width blocks exist (page is likely single-column).
    - No gap of at least 15 pts is found in the target band (also single-col).
    """
    if page_width <= 0:
        return page_width / 2.0

    lo = page_width * 0.30
    hi = page_width * 0.70
    MIN_GAP = 15.0  # pts — ignore hairline gaps

    x0s = set()
    for b in blocks:
        bbox = b.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        # skip full-width anchors — they don't carry column information
        if (bbox[2] - bbox[0]) > 0.7 * page_width:
            continue
        x0s.add(round(bbox[0], 1))

    if len(x0s) < 4:
        return page_width / 2.0

    x0s_sorted = sorted(x0s)
    best_gap: float = 0.0
    best_mid: float = page_width / 2.0

    for i in range(len(x0s_sorted) - 1):
        a, b_val = x0s_sorted[i], x0s_sorted[i + 1]
        gap = b_val - a
        mid_candidate = (a + b_val) / 2.0
        if lo <= mid_candidate <= hi and gap > best_gap:
            best_gap = gap
            best_mid = mid_candidate

    if best_gap >= MIN_GAP:
        logger.debug(
            f"_detect_column_midpoint: auto-detected mid_x={best_mid:.1f} "
            f"(gap={best_gap:.1f} pts, page_width={page_width:.1f})"
        )
        return best_mid

    return page_width / 2.0


# ── 1. PER-PAGE REORDER ───────────────────────────────────────────────────────

def reorder_page_blocks(
    blocks: List[Dict[str, Any]],
    page_width: float,
    mid_x: Optional[float] = None,
    margin: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Re-orders a single page's text blocks to respect column reading order.

    Args:
        blocks:     All text blocks for a single page (any input order).
        page_width: Page width in points (used to detect full-width spans and
                    to derive ``mid_x`` when not supplied).
        mid_x:      Horizontal midpoint separating left from right column.
                    When ``None`` (default), auto-detected per page using
                    :func:`_detect_column_midpoint` — finds the largest x0
                    gap in the middle 30–70 % of the page width.
        margin:     Half-width dead-zone around ``mid_x``.  Default is 5 pts
                    (tight) because ``mid_x`` is now auto-detected to sit
                    inside the gutter, so a large margin is no longer needed
                    and would incorrectly absorb near-gutter blocks.

    Returns:
        Re-ordered block list for the page.
    """
    if not blocks or page_width <= 0:
        return blocks

    # Auto-detect the column midpoint from the page's own x0 distribution
    # when the caller has not supplied an explicit value.
    mid_x = mid_x if mid_x is not None else _detect_column_midpoint(blocks, page_width)

    def _has_bbox(b: Dict[str, Any]) -> bool:
        bbox = b.get("bbox")
        return bbox is not None and len(bbox) == 4

    def is_full_width(b: Dict[str, Any]) -> bool:
        """True when the block spans >70 % of the page — treat as a section break anchor."""
        if not _has_bbox(b):
            return False
        x0, _, x1, _ = b["bbox"]
        return (x1 - x0) > 0.7 * page_width

    def top_y(b: Dict[str, Any]) -> float:
        """bbox[1] is the *top* y in Docling's inverted coordinate system."""
        return b["bbox"][1] if _has_bbox(b) else 0.0

    # ------------------------------------------------------------------
    # Pre-sort by ascending top-y (Docling: y=0 is top-of-page, y increases
    # downward) so anchor block positions are stable and reading order is
    # top-to-bottom.
    # ------------------------------------------------------------------
    sorted_blocks = sorted(blocks, key=lambda b: top_y(b), reverse=False)

    # ------------------------------------------------------------------
    # Split into segments at each full-width block (section-break anchors).
    # Each anchor becomes its own single-element segment so it is always
    # emitted at its natural vertical position.
    # ------------------------------------------------------------------
    segments: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for b in sorted_blocks:
        if is_full_width(b):
            if current:
                segments.append(current)
                current = []
            segments.append([b])          # anchor is its own segment
        else:
            current.append(b)
    if current:
        segments.append(current)

    # ------------------------------------------------------------------
    # For each segment: split into left / right column and sort each
    # column top→bottom (descending top-y in Docling coords).
    # ------------------------------------------------------------------
    ordered: List[Dict[str, Any]] = []
    for seg in segments:
        # Single full-width anchor block — emit as-is
        if len(seg) == 1 and is_full_width(seg[0]):
            ordered.append(seg[0])
            continue

        left_col = [
            b for b in seg
            if not _has_bbox(b) or b["bbox"][0] < mid_x - margin
        ]
        right_col = [
            b for b in seg
            if _has_bbox(b) and b["bbox"][0] >= mid_x - margin
        ]

        # Sort ascending top-y = top-to-bottom reading order
        left_col.sort(key=lambda b: top_y(b), reverse=False)
        right_col.sort(key=lambda b: top_y(b), reverse=False)

        ordered.extend(left_col)
        ordered.extend(right_col)

    return ordered


# ── 2. DOCUMENT-LEVEL WRAPPER ─────────────────────────────────────────────────

def reorder_all_pages(
    text_blocks: List[Dict[str, Any]],
    page_widths: Dict[int, float],
    default_page_width: float = 612.0,   # US Letter — common for UPSC PDFs
) -> List[Dict[str, Any]]:
    """
    Applies :func:`reorder_page_blocks` to every page independently, then
    reassembles the full block list in page order.

    Args:
        text_blocks:        Full document block list (all pages).
        page_widths:        Mapping of ``page_num → page width in points``
                            (obtained from PyMuPDF / fitz at extraction time).
        default_page_width: Fallback width when a page has no entry in
                            ``page_widths``.

    Returns:
        Re-ordered block list (same blocks, new sequence).
    """
    if not text_blocks:
        return text_blocks

    # Group blocks by page number
    pages: Dict[int, List[Dict[str, Any]]] = {}
    for b in text_blocks:
        p = b.get("page_num", 1)
        pages.setdefault(p, []).append(b)

    reordered: List[Dict[str, Any]] = []
    for p_num in sorted(pages.keys()):
        pw = page_widths.get(p_num, default_page_width)
        reordered.extend(reorder_page_blocks(pages[p_num], page_width=pw))

    original_count = len(text_blocks)
    new_count = len(reordered)
    if original_count != new_count:
        logger.warning(
            f"reorder_all_pages: block count changed {original_count} → {new_count}. "
            "Investigate for missing/duplicated blocks."
        )
    else:
        logger.info(
            f"reorder_all_pages: reordered {new_count} blocks across "
            f"{len(pages)} pages."
        )

    return reordered
