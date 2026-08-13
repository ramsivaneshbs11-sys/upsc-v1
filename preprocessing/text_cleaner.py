"""
text_cleaner.py
────────────────
Cleans extracted JSON data prior to chunking.
Filters out boilerplate blocks (headers, footers, page numbers) and normalizes text.
"""

import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

logger = logging.getLogger("text_cleaner")


def clean_extracted_json(json_path: Path) -> Dict[str, Any]:
    """
    Reads an extracted JSON file (handles both v1 Docling and v2 Gemini schemas),
    extracts content blocks (including text, diagrams, and tables row-by-row),
    and filters out boilerplate.

    Returns:
        Dict containing document metadata and sorted list of non-boilerplate blocks.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Standardize Metadata
    meta = data.get("document_metadata", {})
    if not meta:
        meta = {
            "file_name": data.get("source_pdf", "unknown"),
            "extraction_engine": data.get("extraction_engine", "unknown"),
            "total_pages": data.get("total_pages", 0)
        }

    # 2. Normalize blocks and tables from both v1 (flat) and v2 (nested) formats
    raw_blocks = []
    raw_tables = []

    if "pages" in data:
        for page in data["pages"]:
            raw_blocks.extend(page.get("text_blocks", []))
            raw_tables.extend(page.get("tables", []))
    else:
        raw_blocks = data.get("text_blocks", [])
        raw_tables = data.get("tables", [])

    clean_blocks = []

    # 3. Process Text and Diagram Blocks
    for b in raw_blocks:
        # Filter out boilerplate blocks
        if b.get("is_boilerplate", False):
            continue

        b_type       = b.get("type", "paragraph")
        is_diagram   = b_type == "diagram"
        mermaid_code = None

        if is_diagram:
            # Try to get pre-split fields first
            diag_summary = b.get("diagram_summary", "").strip()
            mermaid_code = b.get("mermaid_code", "").strip()

            # Fallback if fields are missing but text contains separator
            if not diag_summary:
                raw_text = b.get("text", "")
                if "---SUMMARY---" in raw_text:
                    parts = raw_text.split("---SUMMARY---", 1)
                    mermaid_code = parts[0].strip()
                    diag_summary = parts[1].strip()
                else:
                    diag_summary = raw_text.strip()

            text = diag_summary

        elif b.get("is_collapsed_blob") and b_type == "paragraph":
            # ── Issue 4: Collapsed blob — split by newlines into sub-blocks ────────
            # block_cleaner.py has already flagged this block. Expand it here.
            raw_text = b.get("text", "").strip()
            lines    = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if len(lines) > 1:
                for line_idx, line in enumerate(lines):
                    clean_blocks.append({
                        "block_id": f"{b.get('block_id')}_line_{line_idx + 1}",
                        "page_num": b.get("page_num", 1),
                        "type":     "paragraph",
                        "text":     line,
                    })
                logger.debug(
                    f"CollapsedBlobSplit: Split block '{b.get('block_id')}' "
                    f"on page {b.get('page_num')} into {len(lines)} sub-blocks."
                )
                continue   # already appended above, skip normal append
            else:
                text = raw_text

        elif b_type == "table_fragment":
            # ── Issue 1: Shredded table — keep as readable paragraph ────────────────
            text = b.get("text", "").strip()

        else:
            text = b.get("text", "").strip()

        block_dict = {
            "block_id": b.get("block_id"),
            "page_num": b.get("page_num", 1),
            "type":     b_type,
            "text":     text,
            "bbox":     b.get("bbox")
        }
        if mermaid_code:
            block_dict["mermaid_code"] = mermaid_code

        clean_blocks.append(block_dict)

    # ── Issue 3: Layout-aware Label/Value pairing ───────────────────────────
    # Group blocks by page. Find blocks that are visually side-by-side where the left
    # block is a short label (≤ 4 words) and the right block is its value (≥ 3 words).
    pages_blocks = defaultdict(list)
    for block in clean_blocks:
        pages_blocks[block.get("page_num", 1)].append(block)

    merged_blocks = []
    for page_num in sorted(pages_blocks.keys()):
        p_blocks = pages_blocks[page_num]
        merged_set = set()
        pairs_to_merge = {}  # left_block_id -> right_block

        for i, block_A in enumerate(p_blocks):
            bbox_A = block_A.get("bbox")
            if not bbox_A or len(bbox_A) < 4:
                continue

            label_text = block_A.get("text", "").strip()
            # Must be a short label block
            if not label_text or len(label_text.split()) > 4:
                continue

            # Must not be table/diagram/blank blocks
            if block_A.get("type") in ("diagram", "table_row", "table_fragment", "blank_page"):
                continue

            y_min_A = min(float(bbox_A[1]), float(bbox_A[3]))
            y_max_A = max(float(bbox_A[1]), float(bbox_A[3]))
            height_A = y_max_A - y_min_A
            if height_A <= 0:
                continue

            best_match_B = None
            best_overlap_ratio = 0.0

            for j, block_B in enumerate(p_blocks):
                if i == j:
                    continue
                bbox_B = block_B.get("bbox")
                if not bbox_B or len(bbox_B) < 4:
                    continue

                value_text = block_B.get("text", "").strip()
                if not value_text or len(value_text.split()) < 3:
                    continue

                if block_B.get("type") in ("diagram", "table_row", "table_fragment", "blank_page"):
                    continue

                # B must be to the right of A
                A_x_right = float(bbox_A[2])
                B_x_left  = float(bbox_B[0])
                if B_x_left < A_x_right - 15.0:  # allow slight overlap
                    continue

                # B must not be way too far to the right
                if B_x_left > A_x_right + 150.0:
                    continue

                y_min_B = min(float(bbox_B[1]), float(bbox_B[3]))
                y_max_B = max(float(bbox_B[1]), float(bbox_B[3]))
                height_B = y_max_B - y_min_B
                if height_B <= 0:
                    continue

                # Calculate vertical overlap
                overlap_min = max(y_min_A, y_min_B)
                overlap_max = min(y_max_A, y_max_B)
                overlap_height = max(0.0, overlap_max - overlap_min)
                min_height = min(height_A, height_B)

                overlap_ratio = overlap_height / min_height
                if overlap_ratio > 0.45:
                    if overlap_ratio > best_overlap_ratio:
                        best_overlap_ratio = overlap_ratio
                        best_match_B = block_B

            if best_match_B and best_match_B["block_id"] not in merged_set:
                pairs_to_merge[block_A["block_id"]] = best_match_B
                merged_set.add(best_match_B["block_id"])

        for block in p_blocks:
            b_id = block["block_id"]
            if b_id in merged_set:
                continue
            if b_id in pairs_to_merge:
                val_block = pairs_to_merge[b_id]
                block["text"] = f"{block['text'].strip()}: {val_block['text'].strip()}"
                logger.debug(
                    f"LabelValueMerge: Merged '{block['text']}' on page {page_num} "
                    f"using layout coordinates."
                )
            # Remove bbox from the final output blocks to keep chunks clean
            block.pop("bbox", None)
            merged_blocks.append(block)

    clean_blocks = merged_blocks

    # 4. Process Table Blocks (Option A: Row + Header Chunking)
    for tbl in raw_tables:
        table_id = tbl.get("table_id")
        page_num = tbl.get("page_num", 1)
        caption = tbl.get("caption", "").strip()
        headers = tbl.get("headers", [])
        rows = tbl.get("rows", [])

        if not rows:
            continue

        caption_prefix = f"Table ({caption}): " if caption else "Table: "

        for row_idx, row in enumerate(rows):
            row_parts = []
            for col_idx, cell in enumerate(row):
                header_name = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx + 1}"
                row_parts.append(f"{header_name}: {cell.strip()}")

            row_text = caption_prefix + " | ".join(row_parts)

            clean_blocks.append({
                "block_id": f"{table_id}_row_{row_idx + 1}",
                "page_num": page_num,
                "type": "table_row",
                "text": row_text
            })

    # 5. Sort stably by page_num so text and table rows of the same page are chunked together
    clean_blocks.sort(key=lambda x: x["page_num"])

    logger.info(
        f"TextCleaner: Retained {len(clean_blocks)} blocks (text, diagrams, and table rows) "
        f"from {json_path.name}"
    )

    return {
        "metadata": meta,
        "blocks": clean_blocks
    }
