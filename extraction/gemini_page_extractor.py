"""
gemini_page_extractor.py
─────────────────────────
Orchestrator for full-document extraction using Gemini 3.5 Flash.

For each page 1…N:
  1. text_service.extract_text()   → text_blocks  (headings, paragraphs, list_items, diagrams)
  2. table_service.extract_tables() → tables       (structured table data)
  3. merge_page()                  → page_json     { page_num, text_blocks, tables }
  4. Completeness check            → log warning if both are empty (blank/image page)

After all pages:
  - Builds and saves a final_json document (same top-level schema as Endpoint 1)
  - Returns (None, final_json) — None for doc object (no Docling doc used here)

Usage:
    from extraction.gemini_page_extractor import extract_document_with_gemini
    _, data = extract_document_with_gemini(pdf_path, output_dir)
"""

import gc
import json
import logging
import time
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF — used only for total_pages count

from extraction.text_service import extract_text
from extraction.table_service import extract_tables
from extraction.gemini_client import GEMINI_MODEL

logger = logging.getLogger("gemini_page_extractor")

_INTER_PAGE_DELAY_SECS = 4.0


# ── Public entry point ────────────────────────────────────────────────────────

def extract_document_with_gemini(
    pdf_path: Path,
    output_dir: Path,
    start_page: int = 1,
    end_page: int = None,
    pages_list: list[int] = None,
) -> tuple[None, dict[str, Any]]:
    """
    Gemini extraction loop supporting custom page range or list of pages.

    Args:
        pdf_path:   Path to the input PDF file.
        output_dir: Directory to save the final extracted JSON.
        start_page: Page to start extraction from (1-indexed).
        end_page:   Page to end extraction at (1-indexed).
        pages_list: Explicit list of page numbers to extract (1-indexed). If provided,
                    start_page and end_page are ignored.
    
    Returns:
        (None, final_json_dict)
        — None stands in place of the Docling doc object (not used here).
        — final_json_dict follows the same schema as Endpoint 1 output for
          preprocessing pipeline compatibility.
    """
    pdf_path   = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # ── Count total pages ─────────────────────────────────────────────────────
    fitz_doc    = fitz.open(str(pdf_path))
    total_pages = len(fitz_doc)
    fitz_doc.close()

    if pages_list is not None:
        # Filter valid pages, remove duplicates, and sort
        pages_to_extract = sorted(list(set([p for p in pages_list if 1 <= p <= total_pages])))
        if not pages_to_extract:
            raise ValueError("No valid pages found in the provided pages_list")
        logger.info(
            f"[gemini_page_extractor] Starting extraction: "
            f"{pdf_path.name} (explicit pages: {pages_to_extract} of {total_pages} total)"
        )
    else:
        if end_page is None:
            end_page = total_pages
        else:
            end_page = min(end_page, total_pages)

        start_page = max(1, start_page)
        if start_page > end_page:
            raise ValueError(f"start_page ({start_page}) cannot be greater than end_page ({end_page})")

        pages_to_extract = list(range(start_page, end_page + 1))
        logger.info(
            f"[gemini_page_extractor] Starting extraction: "
            f"{pdf_path.name} (pages {start_page} to {end_page} of {total_pages} total)"
        )

    pages: list[dict[str, Any]] = []
    blank_pages: list[int]      = []
    total_text_blocks            = 0
    total_tables                 = 0
    total_diagrams               = 0

    start_time = time.time()

    # ── Per-page extraction loop ──────────────────────────────────────────────
    for idx, page_num in enumerate(pages_to_extract):
        logger.info(
            f"[gemini_page_extractor] Page {page_num}/{total_pages} …"
        )

        # 1. Extract text for this page
        try:
            text_blocks = extract_text(pdf_path, page_num)
        except Exception as exc:
            logger.warning(
                f"[gemini_page_extractor] text_service failed on page {page_num}: {exc}"
            )
            text_blocks = []

        # 2. Extract tables for this page
        try:
            tables = extract_tables(pdf_path, page_num)
        except Exception as exc:
            logger.warning(
                f"[gemini_page_extractor] table_service failed on page {page_num}: {exc}"
            )
            tables = []

        # 3. Merge into a single page JSON
        page_json = _merge_page(page_num, text_blocks, tables)

        # 4. Completeness check (quality gate)
        if not text_blocks and not tables:
            logger.warning(
                f"[gemini_page_extractor] Page {page_num}: both services returned empty — "
                f"likely blank or image-only page. Accepting and continuing."
            )
            blank_pages.append(page_num)

        pages.append(page_json)
        # Count diagram blocks separately for the summary
        page_diagrams      = sum(1 for b in text_blocks if b.get("type") == "diagram")
        total_text_blocks += len(text_blocks)
        total_tables      += len(tables)
        total_diagrams    += page_diagrams

        # Free memory after each page
        gc.collect()

        # Small delay to avoid rate-limit errors
        if idx < len(pages_to_extract) - 1:
            time.sleep(_INTER_PAGE_DELAY_SECS)

    elapsed = time.time() - start_time

    # ── Build final document JSON ─────────────────────────────────────────────
    final_json = _build_final_json(
        pdf_path=pdf_path,
        total_pages=total_pages,
        pages=pages,
        total_text_blocks=total_text_blocks,
        total_tables=total_tables,
        total_diagrams=total_diagrams,
        blank_pages=blank_pages,
        elapsed_secs=elapsed,
    )

    # ── Save to disk ──────────────────────────────────────────────────────────
    if pages_list is not None:
        pages_str = "_".join(map(str, pages_to_extract))
        if len(pages_str) > 30:
            pages_str = f"{len(pages_to_extract)}_selected_pages"
        out_name = f"{pdf_path.stem.strip()}_pages_{pages_str}_extracted.json"
    elif start_page == 1 and end_page == total_pages:
        out_name = f"{pdf_path.stem.strip()}_extracted.json"
    else:
        out_name = f"{pdf_path.stem.strip()}_pages_{start_page}_to_{end_page}_extracted.json"
    out_path = output_dir / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    logger.info(
        f"[gemini_page_extractor] Extraction complete: "
        f"{len(pages)} pages processed, {total_text_blocks} text blocks, "
        f"{total_diagrams} diagram(s), {total_tables} tables — "
        f"saved to {out_path} ({elapsed:.1f}s)"
    )

    return None, final_json


# ── Page merger ───────────────────────────────────────────────────────────────

def _merge_page(
    page_num: int,
    text_blocks: list[dict],
    tables: list[dict],
) -> dict[str, Any]:
    """
    Combine text_blocks and tables from both services into a single page dict.
    """
    return {
        "page_num":    page_num,
        "text_blocks": text_blocks,
        "tables":      tables,
    }


# ── Final JSON builder ────────────────────────────────────────────────────────

def _build_final_json(
    pdf_path: Path,
    total_pages: int,
    pages: list[dict],
    total_text_blocks: int,
    total_tables: int,
    total_diagrams: int,
    blank_pages: list[int],
    elapsed_secs: float,
) -> dict[str, Any]:
    """
    Assemble the top-level final JSON document.
    Schema mirrors Endpoint 1 output so the preprocessing pipeline works
    with both extraction engines without modification.
    Includes total_diagrams in the extraction_summary for reporting.
    """
    pages_with_content = len(pages) - len(blank_pages)

    return {
        "source_pdf":          pdf_path.name,
        "extraction_engine":   GEMINI_MODEL,
        "total_pages":         total_pages,
        "extraction_summary": {
            "total_text_blocks":   total_text_blocks,
            "total_diagrams":      total_diagrams,
            "total_tables":        total_tables,
            "pages_with_content":  pages_with_content,
            "blank_pages":         len(blank_pages),
            "blank_page_numbers":  blank_pages,
            "elapsed_seconds":     round(elapsed_secs, 2),
        },
        "pages": pages,
    }
