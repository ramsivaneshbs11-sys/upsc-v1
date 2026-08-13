"""
table_service.py
─────────────────
Extracts all TABLE content from a single PDF page using Gemini 2.5 Flash
Vision LLM.

Used by gemini_page_extractor.py as one of two parallel extraction services
(the other being text_service.py). Results from both are merged per-page.

Public API:
    extract_tables(pdf_path, page_number) -> list[dict]
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from extraction.gemini_client import (
    get_gemini_client,
    render_page_to_jpeg,
    call_gemini,
)

logger = logging.getLogger("table_service")

# ── Prompt ─────────────────────────────────────────────────────────────────────
_TABLE_EXTRACTION_PROMPT = """
You are a precise document table extraction engine.

Your task: Extract ALL tables from this PDF page image.

STRICT RULES:
1. Identify every table present on the page (there may be 0, 1, or more).
2. For each table:
   - Extract the header row as a list of column name strings.
   - Extract all data rows — each row is a list of cell value strings.
   - Transcribe cell values VERBATIM. Do not paraphrase or abbreviate.
   - If a caption or title is present above/below the table, extract it.
3. DO NOT extract any non-table text (headings, paragraphs, captions unrelated to tables).
4. If the page has NO tables, return an empty array [].

Return ONLY a JSON array with this exact structure — no markdown fences, no extra keys:
[
  {
    "caption": "Table 1: Major Dynasties",
    "headers": ["Dynasty", "Period", "Region"],
    "rows": [
      ["Maurya", "322–185 BCE", "North India"],
      ["Gupta", "320–550 CE", "North India"]
    ]
  }
]

If there is no caption, use an empty string "".
If headers cannot be determined, use ["Column_1", "Column_2", ...].
""".strip()

_TABLE_RETRY_PROMPT = """
Your previous response could not be parsed as valid JSON.
Extract all tables from this page image and return ONLY a raw JSON array.
No markdown, no explanation, no code fences. Start your response with [ and end with ].
Each element must have keys: "caption" (string), "headers" (list of strings), "rows" (list of lists of strings).
If no tables exist, return [].
""".strip()


# ── Main public function ───────────────────────────────────────────────────────

def extract_tables(pdf_path: Path, page_number: int) -> list[dict[str, Any]]:
    """
    Extract all tables from a single PDF page via Gemini 2.5 Flash.

    Args:
        pdf_path:    Path to the PDF file.
        page_number: 1-indexed page number.

    Returns:
        List of table dicts. Each table has:
            table_id     (str)  — e.g. "tbl_gemini_p0001_001"
            page_num     (int)
            caption      (str)
            headers      (list[str])
            rows         (list[list[str]])
            row_count    (int)
            column_count (int)
            source       (str)  — "gemini_table_service"

        Returns [] on page with no tables, Gemini block, or unrecoverable parse error.
    """
    pdf_path = Path(pdf_path)
    logger.info(f"[table_service] Extracting tables — page {page_number}")

    try:
        client      = get_gemini_client()
        image_bytes = render_page_to_jpeg(pdf_path, page_number)
    except Exception as exc:
        logger.error(f"[table_service] Setup failed on page {page_number}: {exc}")
        return []

    # ── Attempt 1 ─────────────────────────────────────────────────────────────
    raw    = call_gemini(client, image_bytes, _TABLE_EXTRACTION_PROMPT)
    tables = _parse_table_response(raw, page_number)

    # ── Retry once on parse failure ───────────────────────────────────────────
    if tables is None:
        logger.warning(
            f"[table_service] Parse failed on page {page_number} — retrying with stricter prompt."
        )
        raw2   = call_gemini(client, image_bytes, _TABLE_RETRY_PROMPT)
        tables = _parse_table_response(raw2, page_number)

    if tables is None:
        logger.error(
            f"[table_service] Could not parse Gemini response on page {page_number} after retry. "
            f"Returning empty list."
        )
        return []

    # ── Assign table IDs ──────────────────────────────────────────────────────
    enriched = []
    for idx, tbl in enumerate(tables, start=1):
        headers      = tbl.get("headers", [])
        rows         = tbl.get("rows", [])
        enriched.append({
            "table_id":     f"tbl_gemini_p{page_number:04d}_{idx:03d}",
            "page_num":     page_number,
            "caption":      str(tbl.get("caption", "")).strip(),
            "headers":      [str(h) for h in headers],
            "rows":         [[str(cell) for cell in row] for row in rows],
            "row_count":    len(rows),
            "column_count": len(headers),
            "source":       "gemini_table_service",
        })

    # ── Post-process: fix column misalignment + header duplication ────────────
    enriched = [_postprocess_table(tbl) for tbl in enriched]

    logger.info(
        f"[table_service] Page {page_number}: extracted {len(enriched)} table(s)."
    )
    return enriched


# ── Table Post-Processor ──────────────────────────────────────────────────────

def _postprocess_table(tbl: dict) -> dict:
    """
    Applies two post-processing fixes to a single extracted table:

    Fix A — Issue 6: Duplicate header deduplication.
        If all header cells contain the same string (e.g. a merged title row
        duplicated across columns), replace them with semantically meaningful
        default headers. For a 2-column table (field/value list) use ["Field", "Value"].
        For wider tables fall back to ["Column_1", "Column_2", ...].

    Fix B — Issue 2: Phantom column from word-wrap.
        If a middle column has ALL cells with ≤ 2 words (a sign of wrapped text
        being split at a line break by the PDF extractor), merge those cells back
        INTO THE CORRECT POSITION inside the preceding column's text — NOT appended
        at the end. The fragment is inserted before the last word of the preceding
        cell (which is typically a trailing qualifier like "concept", "cluster").
    """
    headers = tbl.get("headers", [])
    rows    = tbl.get("rows", [])

    # ── Fix A: Duplicate headers ───────────────────────────────────────────────
    if len(headers) > 1 and len(set(h.strip().lower() for h in headers)) == 1:
        logger.info(
            f"[table_service] {tbl['table_id']}: Duplicate header detected — "
            f"replacing with meaningful default headers."
        )
        if len(headers) == 2:
            # 2-column tables are almost always a Field/Value key-value list
            headers = ["Field", "Value"]
        else:
            headers = [f"Column_{i+1}" for i in range(len(headers))]
        tbl["headers"] = headers

    # ── Fix B: Phantom column from word-wrap (word-order-preserving merge) ────
    # Only attempt if there are at least 3 columns and at least 2 rows of data.
    if len(headers) >= 3 and len(rows) >= 2:
        for col_idx in range(1, len(headers) - 1):
            col_cells = []
            for row in rows:
                if col_idx < len(row):
                    col_cells.append(row[col_idx].strip())

            if not col_cells:
                continue

            # If ALL cells in this column are ≤ 2 words, it's a word-wrap artifact
            all_short = all(len(c.split()) <= 2 for c in col_cells)
            if all_short:
                logger.info(
                    f"[table_service] {tbl['table_id']}: Phantom column detected at index "
                    f"{col_idx} — merging fragment into column {col_idx - 1} at correct position."
                )
                for row in rows:
                    if col_idx < len(row):
                        fragment = row.pop(col_idx)
                        fragment = fragment.strip()
                        if not fragment:
                            continue
                        if col_idx - 1 < len(row):
                            prev_cell = row[col_idx - 1].strip()
                            prev_words = prev_cell.split()
                            # The phantom fragment is typically a word that was pushed
                            # to the next column due to line-wrap. It belongs BEFORE the
                            # last word(s) of the preceding cell (which are the trailing
                            # qualifier). Insert before the last word for correct order.
                            if len(prev_words) > 1:
                                row[col_idx - 1] = " ".join(
                                    prev_words[:-1] + [fragment] + [prev_words[-1]]
                                ).strip()
                            else:
                                row[col_idx - 1] = f"{fragment} {prev_cell}".strip()

                headers.pop(col_idx)
                tbl["headers"]      = headers
                tbl["column_count"] = len(headers)
                break

    # Always recompute row_count from actual rows
    tbl["row_count"] = len(rows)
    tbl["rows"]      = rows
    return tbl


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_table_response(raw: str, page_number: int) -> list[dict] | None:
    """
    Parse Gemini's raw text response into a list of table dicts.
    Returns None on failure (caller should retry or give up).
    """
    if not raw or not raw.strip():
        return []

    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.debug(
                    f"[table_service] JSON extraction fallback also failed on page {page_number}."
                )
                return None
        else:
            return None

    if not isinstance(data, list):
        return None

    # Validate and normalise each table entry
    valid: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        headers = item.get("headers", [])
        rows    = item.get("rows", [])

        # Must have at least one header or one row to be a real table
        if not headers and not rows:
            continue

        # Ensure rows is a list of lists
        clean_rows = []
        for row in rows:
            if isinstance(row, list):
                clean_rows.append(row)
            elif isinstance(row, dict):
                # Sometimes Gemini returns rows as dicts — convert to ordered list
                clean_rows.append(list(row.values()))

        valid.append({
            "caption": str(item.get("caption", "")).strip(),
            "headers": [str(h) for h in headers],
            "rows":    clean_rows,
        })

    return valid
