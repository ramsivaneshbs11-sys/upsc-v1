"""
block_cleaner.py
─────────────────
8-pass block cleanup module to fix:
  - Multi-column reading order & Y-coordinate direction (Top-to-Bottom, Left-Column then Right-Column)
  - Watermark noise (`2019-200`, standalone numbers/hyphens)
  - Icon-glyph garbage tokens (`headright`, `boxshadowdwn`)
  - Stylized heading OCR corruption (`Let's recal l` -> `Let's recall`, etc.)
  - Split caption block rejoining
  - Duplicate heading block removal
  - Blank page marker emission for pages with no content          [Issue #3]
  - Full-page placeholder bbox flagging (bbox_approximate=True)  [Issue #10]
"""

import re
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger("block_cleaner")

# Issue #10: Full-page placeholder bbox dimensions (Docling default when coords are missing)
# These are not real positions and should be flagged.
_FULL_PAGE_BBOXES = {
    (0.0, 0.0, 595.0, 842.0),
    (0, 0, 595.0, 842.0),
    (0.0, 0.0, 595.2755737304688, 841.8897705078125),
    (0, 0, 595.2755737304688, 841.8897705078125),
    # US Letter dimensions — Issue 4: Anthropology courseware page 17 blob
    (0.0, 0.0, 612.0, 792.0),
    (0, 0, 612.0, 792.0),
}

def _is_full_page_bbox(bbox) -> bool:
    """Returns True if the bbox is a known full-page placeholder."""
    if not bbox or len(bbox) < 4:
        return False
    key = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return key in _FULL_PAGE_BBOXES

# Regex patterns for stylized handwriting heading corruption fixes
STYLIZED_HEADING_FIXES = [
    (re.compile(r"\bLet['’]s\s+recal\s*l\b", re.IGNORECASE), "Let's recall"),
    (re.compile(r"\bLet['’]s\s+imagin\s*e\b", re.IGNORECASE), "Let's imagine"),
    (re.compile(r"\bLet['’]s\s+(?:discus\s*s|di\s*scus\s*s)\b", re.IGNORECASE), "Let's discuss"),
    (re.compile(r"\bLet['’]s\s+d\s*o\b", re.IGNORECASE), "Let's do"),
]

# Garbage tokens created by OCR on icons/callouts
GARBAGE_TOKENS = {"headright", "boxshadowdwn", "boxshadow"}

# Watermark patterns
WATERMARK_REGEX = re.compile(r"^2019[-–]200?$", re.IGNORECASE)
SINGLE_WATERMARK_CHAR_REGEX = re.compile(r"^[0-9\-–]$")


# Y-band tolerance: blocks whose top-Y values are within this many points are
# considered on the same visual line and sorted left-to-right instead of top-to-bottom.
_SAME_LINE_Y_TOLERANCE = 6.0


def _reading_order_key(block: Dict[str, Any]):
    """
    Sort key for top-to-bottom, left-to-right reading order.

    Docling uses an INVERTED Y-axis (higher Y = nearer top of page).  To read
    top-to-bottom we sort Y DESCENDING.  For two blocks on the same visual line
    (Y values within _SAME_LINE_Y_TOLERANCE) we break the tie by sorting X
    ASCENDING (left-to-right).

    Returns a tuple suitable for Python sort (ascending by default).
    We negate Y so that the highest Y comes first when sorted ascending.
    """
    bbox = block.get("bbox", [0, 0, 0, 0])
    y_top = bbox[1]
    x_left = bbox[0]
    # Snap Y to a grid band so that near-equal Y values are treated identically
    y_band = round(y_top / _SAME_LINE_Y_TOLERANCE) * _SAME_LINE_Y_TOLERANCE
    return (-y_band, x_left)   # negate y_band → top of page sorts first


def _sort_page_reading_order(p_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts page blocks in layout-aware reading order:
      1. Single-column pages: sorted strictly top-to-bottom (Y-descending),
         tie-breaking left-to-right on visual line bands.  A safety bubble-sort
         then corrects any remaining out-of-order adjacent blocks within the
         single column.
      2. Multi-column pages: top headers, left column top-to-bottom, right column
         top-to-bottom, footers.  NO global Y-comparator runs after the split,
         because Docling's inverted-Y system means right-column top-of-page
         blocks have HIGH bbox[1] values but must appear AFTER all left-column
         blocks.  A cross-column bubble-sort would re-interleave them.
    """
    if not p_blocks:
        return []

    # Split into blocks with and without bounding boxes
    valid_blocks = [b for b in p_blocks if b.get("bbox") and len(b.get("bbox")) == 4]
    no_bbox_blocks = [b for b in p_blocks if not (b.get("bbox") and len(b.get("bbox")) == 4)]

    if not valid_blocks:
        return p_blocks

    x_lefts  = [b["bbox"][0] for b in valid_blocks]
    x_rights = [b["bbox"][2] for b in valid_blocks]

    min_x      = min(x_lefts)
    max_x      = max(x_rights)
    page_width = max(max_x - min_x, 100.0)
    x_mid      = min_x + page_width / 2.0

    # ── Multi-column detection (strict) ──────────────────────────────────────
    NARROW_THRESHOLD = 0.50   # block width must be < 50 % of page width
    MIN_BLOCKS_PER_COL = 4    # need at least this many narrow blocks per side
    MIN_COVERAGE_RATIO = 0.60 # narrow blocks must be > 60 % of all body blocks

    narrow_blocks = [
        b for b in valid_blocks
        if (b["bbox"][2] - b["bbox"][0]) / page_width < NARROW_THRESHOLD
    ]
    left_narrow  = [b for b in narrow_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 <  x_mid]
    right_narrow = [b for b in narrow_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 >= x_mid]

    is_multi_column = (
        len(left_narrow)  >= MIN_BLOCKS_PER_COL
        and len(right_narrow) >= MIN_BLOCKS_PER_COL
        and len(narrow_blocks) / max(len(valid_blocks), 1) > MIN_COVERAGE_RATIO
    )

    if is_multi_column:
        top_headers = [b for b in valid_blocks if b.get("type") == "header"]
        footers     = [b for b in valid_blocks if b.get("type") == "footer"]
        body_blocks = [b for b in valid_blocks if b not in top_headers and b not in footers]

        left_col  = [b for b in body_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 <  x_mid]
        right_col = [b for b in body_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 >= x_mid]
        top_headers.sort(key=_reading_order_key)
        footers.sort(key=_reading_order_key)
        left_col.sort(key=_reading_order_key)
        right_col.sort(key=_reading_order_key)
        res = top_headers + left_col + right_col + footers
        logger.debug(
            f"Multi-column layout detected: {len(left_col)} left / {len(right_col)} right blocks. "
            "Cross-column bubble-sort skipped to preserve left-then-right reading order."
        )
        # A cross-column swap would re-interleave them.
    else:
        res = sorted(valid_blocks, key=_reading_order_key)

        # ── Single-column safety sort ─────────────────────────────────────────
        # For single-column pages only: ensure no block later in res is physically
        # HIGHER on page (top-Y greater by >20pt) than the one before it.
        # This corrects any edge-case misordering without touching multi-column layout.
        for _ in range(len(res)):
            swapped = False
            for i in range(len(res) - 1):
                if res[i + 1]["bbox"][1] > res[i]["bbox"][1] + 20.0:
                    res[i], res[i + 1] = res[i + 1], res[i]
                    swapped = True
            if not swapped:
                break

    return res + no_bbox_blocks


HEADER_PHRASES = {
    "social science - part i", "social science - part 1", "social science part 1",
    "social science part i", "india's struggle for independence", "the heritage of india",
}

HEADING_PATTERNS = [
    re.compile(r"^\s*chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^\s*exercises\s*$", re.IGNORECASE),
    re.compile(r"^\s*things\s+to\s+know\b", re.IGNORECASE),
    re.compile(r"^\s*india['’]?s\s+struggle\s+for\s+independence\b", re.IGNORECASE),
    re.compile(r"^\s*revolt\s+of\s+1857\b", re.IGNORECASE),
    re.compile(r"^\s*rise\s+of\s+indian\s+nationalism\b", re.IGNORECASE),
    re.compile(r"^\s*indian\s+national\s+congress\b", re.IGNORECASE),
    re.compile(r"^\s*boycott\s+and\s+swadeshi\b", re.IGNORECASE),
    re.compile(r"^\s*morley[- ]minto\b", re.IGNORECASE),
    re.compile(r"^\s*khilafat\b", re.IGNORECASE),
    re.compile(r"^\s*non[- ]cooperation\b", re.IGNORECASE),
    re.compile(r"^\s*civil\s+disobedience\b", re.IGNORECASE),
    re.compile(r"^\s*quit\s+india\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+medieval\s+period\b", re.IGNORECASE),
    re.compile(r"^\s*languages?\s+and\s+literature\b", re.IGNORECASE),
    re.compile(r"^\s*architecture\b", re.IGNORECASE),
    re.compile(r"^\s*cave\s*architecture\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+heritage\s+of\s+india\b", re.IGNORECASE),
]

LIST_PATTERN = re.compile(r"^\s*(\d+[\.\)]|[a-z][\.\)]|[•\-\➢])\s+", re.IGNORECASE)
FOOTER_NUM_PATTERN = re.compile(r"^\s*\d{1,3}\s*$")


def _deduplicate_pages(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects and drops duplicate pages (e.g. pages 22-23 duplicating pages 20-21).
    Checks:
      1. High Jaccard word similarity across non-boilerplate body text between adjacent pages.
    """
    if not blocks:
        return blocks

    pages: Dict[int, List[Dict[str, Any]]] = {}
    for b in blocks:
        p = b.get("page_num")
        if isinstance(p, int):
            pages.setdefault(p, []).append(b)

    page_texts: Dict[int, str] = {}
    for p, p_blks in pages.items():
        text_content = " ".join([
            b.get("text", "") for b in p_blks
            if not b.get("is_boilerplate") and b.get("type") not in ("header", "footer")
        ])
        norm_text = re.sub(r"\s+", " ", text_content).strip().lower()
        page_texts[p] = norm_text

    duplicate_pages = set()
    sorted_pages = sorted(page_texts.keys())

    for i, p in enumerate(sorted_pages):
        p_text = page_texts[p]
        if len(p_text) < 60:
            continue

        w_p = set(p_text.split())
        for prev_p in sorted_pages[max(0, i-4):i]:
            prev_text = page_texts[prev_p]
            if len(prev_text) < 60:
                continue

            w_prev = set(prev_text.split())
            jaccard = len(w_p & w_prev) / float(len(w_p | w_prev)) if (w_p | w_prev) else 0.0

            # True duplicate pages (e.g. pages 22-23 duplicating pages 20-21) share >80% word similarity
            # or >50% word similarity when containing specific section titles like "cave architecture"
            if jaccard >= 0.80 or (jaccard >= 0.50 and ("cave architecture" in p_text or "gandhara" in p_text)):
                logger.info(f"PageDeduplicator: Page {p} is duplicate of Page {prev_p} (Jaccard: {jaccard:.2f}). Dropping Page {p}.")
                duplicate_pages.add(p)
                break

    if duplicate_pages:
        filtered_blocks = [b for b in blocks if b.get("page_num") not in duplicate_pages]
        logger.info(f"PageDeduplicator: Removed {len(blocks) - len(filtered_blocks)} blocks across {len(duplicate_pages)} duplicate pages ({sorted(list(duplicate_pages))})")
        return filtered_blocks

    return blocks


def _split_scanned_collapsed_pages(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies single-paragraph collapsed page blocks (pages 66-93) and splits them into
    well-structured header, footer, heading, list_item, and paragraph blocks.
    """
    new_blocks = []
    for b in blocks:
        text = b.get("text", "")
        # If a block is an overly long single paragraph (>400 chars with linebreaks)
        if b.get("type") == "paragraph" and len(text) > 400 and "\n" in text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            page_num = b.get("page_num", 1)
            bbox = b.get("bbox")

            body_lines = []
            for line in lines:
                l_lower = line.lower()
                if l_lower in HEADER_PHRASES:
                    new_blocks.append({
                        "block_id": "blk_tmp",
                        "page_num": page_num,
                        "type": "header",
                        "text": line,
                        "bbox": bbox
                    })
                elif FOOTER_NUM_PATTERN.match(line) and len(line) <= 3:
                    new_blocks.append({
                        "block_id": "blk_tmp",
                        "page_num": page_num,
                        "type": "footer",
                        "text": line,
                        "bbox": bbox
                    })
                elif any(p.search(line) for p in HEADING_PATTERNS):
                    new_blocks.append({
                        "block_id": "blk_tmp",
                        "page_num": page_num,
                        "type": "heading",
                        "text": line,
                        "bbox": bbox
                    })
                elif LIST_PATTERN.search(line):
                    new_blocks.append({
                        "block_id": "blk_tmp",
                        "page_num": page_num,
                        "type": "list_item",
                        "text": line,
                        "bbox": bbox
                    })
                else:
                    body_lines.append(line)

            if body_lines:
                curr_para = []
                for line in body_lines:
                    if LIST_PATTERN.search(line) and curr_para:
                        new_blocks.append({
                            "block_id": "blk_tmp",
                            "page_num": page_num,
                            "type": "paragraph",
                            "text": " ".join(curr_para),
                            "bbox": bbox
                        })
                        curr_para = [line]
                    else:
                        curr_para.append(line)
                if curr_para:
                    new_blocks.append({
                        "block_id": "blk_tmp",
                        "page_num": page_num,
                        "type": "paragraph",
                        "text": " ".join(curr_para),
                        "bbox": bbox
                    })
        else:
            new_blocks.append(b)

    return new_blocks


def clean_extracted_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Applies multi-pass cleaning pipeline to extracted text blocks.
    """
    if not blocks:
        return []

    # Pass 0: Page Deduplication
    blocks = _deduplicate_pages(blocks)

    # Pass 0b: Split Scanned Collapsed Page Blocks
    blocks = _split_scanned_collapsed_pages(blocks)

    # Pass 1: Watermark & Garbage Token Removal + Empty Block Elimination
    cleaned_pass1 = []
    for b in blocks:
        text = b.get("text", "").strip()

        # Drop any block with empty text (except blank_page structural markers)
        if not text and b.get("type") != "blank_page":
            continue

        # Remove icon garbage tokens
        if text.lower() in GARBAGE_TOKENS:
            continue

        # Remove single character watermark tokens or watermark footer strings
        if SINGLE_WATERMARK_CHAR_REGEX.match(text) and b.get("type") in ("paragraph", "footer"):
            continue
        if WATERMARK_REGEX.match(text):
            continue

        cleaned_pass1.append(b)

    # Pass 2: Stylized Heading Text Fixes
    for b in cleaned_pass1:
        text = b.get("text", "")
        for pattern, replacement in STYLIZED_HEADING_FIXES:
            if pattern.search(text):
                text = pattern.sub(replacement, text)
                b["text"] = text
                if "let's" in replacement.lower() and b.get("type") == "paragraph":
                    b["type"] = "heading"

    # Pass 3: Double-Column & Top-to-Bottom Reading Order Sorting by bbox
    pages: Dict[int, List[Dict[str, Any]]] = {}
    for b in cleaned_pass1:
        p = b.get("page_num", 1)
        pages.setdefault(p, []).append(b)

    sorted_blocks = []
    for p in sorted(pages.keys()):
        sorted_p_blocks = _sort_page_reading_order(pages[p])
        sorted_blocks.extend(sorted_p_blocks)

    # Pass 3b: Issue #10 — Flag full-page placeholder bboxes
    for b in sorted_blocks:
        bbox = b.get("bbox")
        if _is_full_page_bbox(bbox):
            b["bbox_approximate"]  = True
            b["is_collapsed_blob"] = True   # Issue 4: signals text_cleaner to split by newline
            logger.debug(
                f"CollapsedBlob: Block '{b.get('block_id')}' on page {b.get('page_num')} "
                f"has a full-page bbox — flagged as collapsed blob."
            )

    # Pass 4: Rejoin Split Captions on the same page
    rejoined_blocks = []
    idx = 0
    while idx < len(sorted_blocks):
        curr = sorted_blocks[idx]
        if curr.get("type") == "caption" and idx + 1 < len(sorted_blocks):
            nxt = sorted_blocks[idx + 1]
            if (
                nxt.get("type") == "caption"
                and nxt.get("page_num") == curr.get("page_num")
                and not curr["text"].endswith((".", "?", "!"))
            ):
                curr["text"] = f"{curr['text']} {nxt['text']}"
                rejoined_blocks.append(curr)
                idx += 2
                continue
        rejoined_blocks.append(curr)
        idx += 1

    # Pass 5: Heading Deduplication
    deduped_blocks = []
    for b in rejoined_blocks:
        if (
            deduped_blocks
            and b.get("type") == "heading"
            and deduped_blocks[-1].get("type") == "heading"
            and b.get("page_num") == deduped_blocks[-1].get("page_num")
            and b.get("text", "").strip().lower() == deduped_blocks[-1].get("text", "").strip().lower()
        ):
            continue
        deduped_blocks.append(b)

    # Pass 6b: Issue 1 — Shredded table fragment detection & merge
    # If a page has ≥ 15 consecutive heading-typed blocks AND any of them starts with
    # a numeric prefix ("1.", "2.", ...), Docling has mistaken table rows for headings.
    # Fix: filter out boilerplate lines, sort by Y-desc then X-asc for reading order,
    # and set bbox=None (the first_block bbox was wrong — a footer bbox, not a table bbox).
    _NUMBERED_PREFIX = re.compile(r'^\d+\.\s')
    _MIN_SHREDDED_FRAGMENTS = 15
    # Boilerplate phrases that sneak into shredded table fragments
    _SHRED_BOILERPLATE = re.compile(
        r'^(anthropology|formation of new population and species|\d{1,3})$',
        re.IGNORECASE
    )

    pages_headings: Dict[int, List[int]] = {}   # page_num -> list of indices in deduped_blocks
    for i, b in enumerate(deduped_blocks):
        if b.get("type") == "heading":
            p = b.get("page_num", 0)
            pages_headings.setdefault(p, []).append(i)

    shredded_pages: Set[int] = set()
    for p, indices in pages_headings.items():
        heading_texts = [deduped_blocks[i].get("text", "") for i in indices]
        has_numbered  = any(_NUMBERED_PREFIX.match(t.strip()) for t in heading_texts)
        if len(indices) >= _MIN_SHREDDED_FRAGMENTS and has_numbered:
            shredded_pages.add(p)
            logger.info(
                f"ShredTable: Page {p} has {len(indices)} heading fragments with numeric "
                f"prefixes — merging into table_fragment block."
            )

    if shredded_pages:
        merged_blocks: List[Dict[str, Any]] = []
        for p in shredded_pages:
            indices = pages_headings[p]
            # Sort fragment blocks by reading order: Y-descending (top of page first in
            # Docling's inverted Y), then X-ascending (left-to-right)
            frag_blocks = [deduped_blocks[i] for i in indices]
            def _frag_sort_key(b):
                bbox = b.get("bbox") or [0, 0, 0, 0]
                return (-float(bbox[1]), float(bbox[0]))
            frag_blocks_sorted = sorted(frag_blocks, key=_frag_sort_key)
            # Filter out boilerplate lines that leaked into the heading fragments
            frag_texts = [
                b.get("text", "").strip() for b in frag_blocks_sorted
                if not _SHRED_BOILERPLATE.match(b.get("text", "").strip())
                and b.get("text", "").strip()
            ]
            merged_blocks.append({
                "block_id":       f"blk_shred_p{p}",
                "page_num":       p,
                "type":           "table_fragment",
                "text":           "\n".join(frag_texts),
                "bbox":           None,   # first_block bbox was a footer bbox — not valid for table
                "is_boilerplate": False,
                "was_corrected":  True,
                "entities":       [],
                "note":           f"Merged {len(frag_texts)} shredded heading fragments "
                                  f"(Docling table mis-detection on page {p}), sorted by reading order."
            })

        # Rebuild deduped_blocks: drop shredded heading indices, insert merged blocks
        rebuilt: List[Dict[str, Any]] = []
        shredded_indices = {i for p in shredded_pages for i in pages_headings[p]}
        for i, b in enumerate(deduped_blocks):
            if i in shredded_indices:
                continue
            rebuilt.append(b)
        # Insert merged table_fragment blocks in page order
        for mb in merged_blocks:
            insert_pos = next(
                (j for j, b in enumerate(rebuilt) if b.get("page_num", 0) >= mb["page_num"]),
                len(rebuilt)
            )
            rebuilt.insert(insert_pos, mb)
        deduped_blocks = rebuilt
    # Pass 6: Issue #3 — Emit blank-page markers for pages with no non-boilerplate content
    # Collect all page numbers seen
    if deduped_blocks:
        all_pages = pages.keys()
        non_bp_pages: Set[int] = set()
        for b in deduped_blocks:
            if not b.get("is_boilerplate", False) and b.get("type") not in ("footer", "header", "toc_page_number"):
                non_bp_pages.add(b.get("page_num", 0))

        blank_page_markers = []
        for p in sorted(all_pages):
            if p not in non_bp_pages:
                blank_page_markers.append({
                    "block_id": "blk_tmp",
                    "page_num": p,
                    "type": "blank_page",
                    "text": "",
                    "bbox": None,
                    "is_boilerplate": False,
                    "boilerplate_type": None,
                    "was_corrected": False,
                    "entities": [],
                    "note": "Page contains only boilerplate (headers/footers/page-numbers) or no extractable content."
                })
        if blank_page_markers:
            logger.info(f"BlankPageMarker: Emitting {len(blank_page_markers)} blank/cover page marker(s) "
                        f"for pages: {[b['page_num'] for b in blank_page_markers]}")
            # Insert blank-page markers in page-number order
            merged_with_blanks = []
            blank_idx = 0
            for b in deduped_blocks:
                while blank_idx < len(blank_page_markers) and \
                      blank_page_markers[blank_idx]["page_num"] < b.get("page_num", 0):
                    merged_with_blanks.append(blank_page_markers[blank_idx])
                    blank_idx += 1
                merged_with_blanks.append(b)
            # Append any remaining blank markers after all blocks
            while blank_idx < len(blank_page_markers):
                merged_with_blanks.append(blank_page_markers[blank_idx])
                blank_idx += 1
            deduped_blocks = merged_with_blanks

    # Re-assign sequential block IDs
    for idx, b in enumerate(deduped_blocks, start=1):
        b["block_id"] = f"blk_{idx:04d}"

    # Pass 7: Issue 5 — Header/footer reclassification by vertical position
    # Two blocks in the same horizontal band should have the same type.
    # Use bbox[1] (top-Y in Docling's inverted-Y = high value means near top of page).
    # Page height is approximated from the max Y seen across all blocks on the page.
    _TOP_BAND_RATIO    = 0.85   # bbox[1] > 85% of page_height → it's a header (near top)
    _BOTTOM_BAND_RATIO = 0.15   # bbox[1] < 15% of page_height → it's a footer (near bottom)

    # Compute per-page height from max bbox[1] seen
    page_max_y: Dict[int, float] = {}
    for b in deduped_blocks:
        bbox = b.get("bbox")
        if bbox and len(bbox) == 4:
            p = b.get("page_num", 1)
            page_max_y[p] = max(page_max_y.get(p, 0.0), float(bbox[1]))

    reclassified = 0
    for b in deduped_blocks:
        bbox = b.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        p      = b.get("page_num", 1)
        max_y  = page_max_y.get(p, 792.0)
        if max_y == 0:
            continue
        y_top  = float(bbox[1])
        ratio  = y_top / max_y

        old_type = b.get("type", "")
        # Issue 3 fix: protect body-metadata paragraph blocks near the top of page
        # from being wrongly reclassified as 'header'.
        # These are short label blocks like "Paper No.", "Module :" that happen to be
        # in the upper portion of the page but are NOT running page headers.
        text = b.get("text", "").strip()
        is_metadata_label = (
            old_type == "paragraph"
            and len(text.split()) <= 4
            and not b.get("is_boilerplate", False)
        )
        if old_type in ("header", "footer", "paragraph", "heading"):
            if ratio >= _TOP_BAND_RATIO and old_type != "header" and not is_metadata_label:
                b["type"] = "header"
                reclassified += 1
            elif ratio <= _BOTTOM_BAND_RATIO and old_type != "footer":
                b["type"] = "footer"
                reclassified += 1

    if reclassified:
        logger.info(
            f"HeaderFooterReclassify: Reclassified {reclassified} blocks by vertical position."
        )

    logger.info(f"Block cleaner pass complete: Input {len(blocks)} blocks -> Output {len(deduped_blocks)} cleaned blocks")
    return deduped_blocks
