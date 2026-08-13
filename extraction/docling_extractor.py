"""
docling_extractor.py
─────────────────────
Core extraction engine using Docling to parse UPSC PDFs into structured representations.

Pipeline steps per document:
  0. PDF Type Auto-Detection (SCANNED vs DIGITAL via pdf_type_detector.py)
  1. PDF Loading & Layout Parsing (Docling DocumentConverter)
  2. Incomplete Coverage Retry Fallback
  3. Element Classification (Headings, Paragraphs, Lists, Tables)
  4. Hybrid Fitz + Per-Page RapidOCR Fallback (Guarantees 100% Page Coverage for any skipped/crashed pages)
  5. Post-processing Pipeline:
     - Watermark, icon glyph, and 7-pass block cleaner (block_cleaner.py)
     - Boilerplate detection (headers, footers, page numbers)
     - Text content correction (hyphen joins, ligature fixes, abbreviation normalization)
     - Named Entity Recognition (UPSC key terms, dates, acts, articles)

Returns raw Docling document object and processed block list.
"""

import sys
import re
import logging
import os
import gc
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Set

import fitz  # PyMuPDF
import numpy as np

# Set environment variables to prevent threadpool RAM allocation spikes
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

logger = logging.getLogger("docling_extractor")

# Docling imports
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning("Docling library not installed. Install via: pip install docling docling-core")

# RapidOCR import for fallback
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_AVAILABLE = True
except ImportError:
    RAPID_OCR_AVAILABLE = False

# Import postprocessor & cleaner modules
from extraction.pdf_type_detector import is_scanned_pdf
from extraction.block_cleaner import clean_extracted_blocks
from extraction.boilerplate_detector import tag_boilerplate_blocks
from extraction.content_corrector import correct_extracted_blocks
from extraction.ner_extractor import enrich_blocks_with_ner
from extraction.config import DOCLING_PIPELINE_OPTIONS
from extraction.reorder_blocks import reorder_all_pages
from extraction.callout_detector import tag_callout_blocks


# ── 1. DOCLING CONVERTER INITIALIZATION ───────────────────────────────────────

def get_docling_converter(
    do_ocr: bool = False,
    do_table_structure: bool = False,
    generate_page_images: bool = False
) -> Any:
    """
    Builds and configures a Docling DocumentConverter instance.
    """
    if not DOCLING_AVAILABLE:
        raise ImportError("Docling is not installed. Run: pip install docling")

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = do_table_structure
    pipeline_options.generate_page_images = generate_page_images

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    return converter


# ── 2. ELEMENT PARSER ─────────────────────────────────────────────────────────

def parse_docling_elements(doc: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts text blocks and tables from a converted Docling document object.

    Returns:
        (text_blocks, tables)
    """
    text_blocks: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []

    block_id_counter = 1

    # Extract text items
    if hasattr(doc, "texts"):
        for item in doc.texts:
            text = getattr(item, "text", "").strip()
            if not text:
                continue

            # Determine element label/type
            label = "paragraph"
            if hasattr(item, "label"):
                label_str = str(item.label).lower()
                if "heading" in label_str or "title" in label_str or "section" in label_str:
                    label = "heading"
                elif "list" in label_str:
                    label = "list_item"
                elif "caption" in label_str:
                    label = "caption"
                elif "footnote" in label_str:
                    label = "footnote"
                elif "header" in label_str:
                    label = "header"
                elif "footer" in label_str:
                    label = "footer"

            # Page number
            page_num = 1
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                if hasattr(prov, "page_no"):
                    page_num = prov.page_no

            # Bounding box
            bbox = None
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                if hasattr(prov, "bbox") and prov.bbox:
                    b = prov.bbox
                    if hasattr(b, "l"):
                        bbox = [b.l, b.t, b.r, b.b]
                    elif isinstance(b, (list, tuple)):
                        bbox = list(b)

            text_blocks.append({
                "block_id": f"blk_{block_id_counter:04d}",
                "page_num": page_num,
                "type": label,
                "text": text,
                "bbox": bbox
            })
            block_id_counter += 1

    # Extract tables
    if hasattr(doc, "tables"):
        for tbl_idx, table in enumerate(doc.tables, start=1):
            table_dict = _export_docling_table(table, tbl_idx)
            if table_dict:
                tables.append(table_dict)

    return text_blocks, tables


def _export_docling_table(table: Any, tbl_idx: int) -> Dict[str, Any]:
    """Helper to export a Docling table object into a structured dict."""
    page_num = 1
    if hasattr(table, "prov") and table.prov:
        prov = table.prov[0] if isinstance(table.prov, list) else table.prov
        if hasattr(prov, "page_no"):
            page_num = prov.page_no

    headers = []
    rows = []

    if hasattr(table, "export_to_dataframe"):
        try:
            df = table.export_to_dataframe()
            headers = [str(c) for c in df.columns]
            rows = df.astype(str).values.tolist()
            # Clean placeholder text
            headers = [h if "<!--" not in h else f"Col_{i+1}" for i, h in enumerate(headers)]
            rows = [[cell if "<!--" not in cell else "" for cell in row] for row in rows]
        except Exception:
            pass

    # If dataframe export produced no rows or pure placeholders, fallback to docling data model cells
    if not rows and hasattr(table, "data") and hasattr(table.data, "grid"):
        try:
            grid = table.data.grid
            if grid:
                raw_grid = [[cell.text.strip() if hasattr(cell, "text") else str(cell) for cell in row] for row in grid]
                if raw_grid:
                    headers = raw_grid[0]
                    rows = raw_grid[1:]
        except Exception:
            pass

    caption = ""
    if hasattr(table, "caption"):
        caption = str(table.caption or "").strip()

    # Clean generic integer headers (e.g. ['0', '1'] in TOC tables)
    if headers and all(h.isdigit() for h in headers):
        if len(headers) == 2:
            headers = ["Section / Unit", "Page Number"]
        else:
            headers = [f"Column_{int(h)+1}" for h in headers]

    # ── Issue 2 & 3 Fixes: Table Cleaning & Citation Extraction ───────────────────
    # 1. Clean boilerplate running headers from headers and row cells
    BOILERPLATE_PATTERNS = [
        r"(?i)india:\s*6\s*th\s*century\s*bce\s*to\s*200\s*bce",
        r"(?i)^\s*page\s+nos?\.\s*$",
        r"(?i)^\s*bhic-101\s*$",
    ]
    compiled_bp = [re.compile(p) for p in BOILERPLATE_PATTERNS]

    # Check if column 0 is a phantom column containing boilerplate text
    if headers and rows:
        col0_is_bp = True
        for row in rows:
            c0 = row[0].strip() if len(row) > 0 else ""
            if c0 and not any(bp.search(c0) for bp in compiled_bp):
                col0_is_bp = False
                break
        if col0_is_bp:
            headers = headers[1:] if len(headers) > 1 else []
            rows = [r[1:] for r in rows if len(r) > 1]

    # 2. Extract citation footnotes absorbed into the last table rows (Issue 3 fix)
    CITATION_REGEX = re.compile(r"^\s*\(.*?(?:Kumar|MHI|Block|Unit|p\.\s*\d+|Press|Edition|ISBN|Source|Adapted).*?\)\s*$", re.IGNORECASE)
    cleaned_rows = []
    for r in rows:
        r_text = " ".join([cell.strip() for cell in r if cell.strip()])
        if CITATION_REGEX.search(r_text):
            if not caption:
                caption = r_text
            else:
                caption = f"{caption} ({r_text})"
        else:
            cleaned_rows.append(r)
    rows = cleaned_rows

    return {
        "table_id": f"tbl_{tbl_idx:03d}",
        "page_num": page_num,
        "caption": caption,
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(headers)
    }


# ── 3. HYBRID PYMUPDF + PER-PAGE RAPIDOCR FALLBACK (100% Coverage Guarantee) ──

def _fill_missing_pages_via_fitz(pdf_path: Path, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Checks if any PDF pages were skipped or rendered near-empty (<50 chars) by Docling.
    Executes targeted 300 DPI RapidOCR recovery to guarantee complete content capture.

    IMPORTANT — de-duplication behaviour:
    If a page already has some blocks (low-content, < 20 chars total), those blocks
    are REMOVED before appending the recovered text so we do not create duplicates.
    """
    try:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return text_blocks

        # Calculate character counts and block counts per page
        page_char_counts: Dict[int, int] = {}
        page_block_counts: Dict[int, int] = {}
        page_max_block_len: Dict[int, int] = {}

        for b in text_blocks:
            p = b.get("page_num")
            if isinstance(p, int):
                blen = len(b.get("text", ""))
                page_char_counts[p] = page_char_counts.get(p, 0) + blen
                page_block_counts[p] = page_block_counts.get(p, 0) + (0 if b.get("is_boilerplate") else 1)
                if not b.get("is_boilerplate"):
                    page_max_block_len[p] = max(page_max_block_len.get(p, 0), blen)

        covered_pages = set(page_char_counts.keys())
        missing_pages = set(range(1, total_pages + 1)) - covered_pages

        # Flag truly blank pages (<20 chars) for re-OCR check
        low_content_pages = {p for p in range(1, total_pages + 1) if page_char_counts.get(p, 0) < 20}

        # Fix 1 / Issue 1: Detect collapsed-blob pages — pages where Docling's TableFormer
        # ran out of RAM (std::bad_alloc) and silently dumped the whole page as one giant
        # paragraph instead of proper heading/list structure.
        # Heuristic: ≤3 non-boilerplate blocks AND max single block len > 400 chars.
        collapsed_blob_pages = {
            p for p in range(1, total_pages + 1)
            if (page_block_counts.get(p, 0) <= 3
                and page_max_block_len.get(p, 0) > 400)
        }

        if collapsed_blob_pages:
            logger.info(
                f"Hybrid Fitz Fallback: detected {len(collapsed_blob_pages)} collapsed-blob page(s) "
                f"(Docling TableFormer OOM degradation). Scheduling structured re-extraction."
            )

        pages_to_recover = missing_pages.union(low_content_pages).union(collapsed_blob_pages)

        if not pages_to_recover:
            doc.close()
            return text_blocks


        logger.info(
            f"Hybrid Fitz Fallback: Triggering targeted recovery for {len(pages_to_recover)} pages "
            f"({sorted(list(pages_to_recover))})..."
        )

        ocr_engine = RapidOCR() if RAPID_OCR_AVAILABLE else None

        for p_num in sorted(list(pages_to_recover)):
            page = doc[p_num - 1]
            text = page.get_text().strip()

            # Run 150 DPI Preprocessed Scan OCR if page native text is thin/empty
            if len(text) < 50 and ocr_engine:
                try:
                    pix = page.get_pixmap(dpi=150)
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

                    # 300 DPI Scan Image Preprocessing (Grayscale + Otsu Binarization for sharp letter edges)
                    try:
                        import cv2
                        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        img_for_ocr = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
                    except Exception:
                        img_for_ocr = img

                    res, _ = ocr_engine(img_for_ocr)
                    if res:
                        pw, ph = pix.width, pix.height
                        x_mid = pw / 2.0

                        headers, footers, col1, col2 = [], [], [], []
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
                            re.compile(r"^\s*non[- ]cooperation\b", re.IGNORECASE),
                            re.compile(r"^\s*civil\s+disobedience\b", re.IGNORECASE),
                            re.compile(r"^\s*quit\s+india\b", re.IGNORECASE),
                        ]
                        LIST_PATTERN = re.compile(r"^\s*(\d+[\.\)]|[a-z][\.\)]|[•\-\➢])\s+", re.IGNORECASE)
                        FOOTER_NUM_PATTERN = re.compile(r"^\s*\d{1,3}\s*$")

                        for item in res:
                            box, line_text, score = item[0], item[1].strip(), item[2]
                            if not line_text:
                                continue
                            xc = (box[0][0] + box[1][0] + box[2][0] + box[3][0]) / 4.0
                            yc = (box[0][1] + box[1][1] + box[2][1] + box[3][1]) / 4.0

                            t_low = line_text.lower()
                            if yc < ph * 0.08 or t_low in HEADER_PHRASES:
                                headers.append(line_text)
                            elif yc > ph * 0.92 or (FOOTER_NUM_PATTERN.match(line_text) and len(line_text) <= 3):
                                footers.append(line_text)
                            elif xc < x_mid:
                                col1.append((yc, line_text))
                            else:
                                col2.append((yc, line_text))

                        col1.sort(key=lambda x: x[0])
                        col2.sort(key=lambda x: x[0])

                        page_recovered_blocks = []
                        for h in headers:
                            page_recovered_blocks.append({
                                "block_id": f"blk_rec_p{p_num:04d}",
                                "page_num": p_num,
                                "type": "header",
                                "text": h,
                                "bbox": [0, 0, page.rect.width, page.rect.height]
                            })

                        all_body_lines = [t for y, t in col1] + [t for y, t in col2]
                        curr_para = []
                        for line in all_body_lines:
                            if any(hp.search(line) for hp in HEADING_PATTERNS):
                                if curr_para:
                                    page_recovered_blocks.append({
                                        "block_id": f"blk_rec_p{p_num:04d}",
                                        "page_num": p_num,
                                        "type": "paragraph",
                                        "text": " ".join(curr_para),
                                        "bbox": [0, 0, page.rect.width, page.rect.height]
                                    })
                                    curr_para = []
                                page_recovered_blocks.append({
                                    "block_id": f"blk_rec_p{p_num:04d}",
                                    "page_num": p_num,
                                    "type": "heading",
                                    "text": line,
                                    "bbox": [0, 0, page.rect.width, page.rect.height]
                                })
                            elif LIST_PATTERN.search(line):
                                if curr_para:
                                    page_recovered_blocks.append({
                                        "block_id": f"blk_rec_p{p_num:04d}",
                                        "page_num": p_num,
                                        "type": "paragraph",
                                        "text": " ".join(curr_para),
                                        "bbox": [0, 0, page.rect.width, page.rect.height]
                                    })
                                    curr_para = []
                                page_recovered_blocks.append({
                                    "block_id": f"blk_rec_p{p_num:04d}",
                                    "page_num": p_num,
                                    "type": "list_item",
                                    "text": line,
                                    "bbox": [0, 0, page.rect.width, page.rect.height]
                                })
                            else:
                                curr_para.append(line)

                        if curr_para:
                            page_recovered_blocks.append({
                                "block_id": f"blk_rec_p{p_num:04d}",
                                "page_num": p_num,
                                "type": "paragraph",
                                "text": " ".join(curr_para),
                                "bbox": [0, 0, page.rect.width, page.rect.height]
                            })

                        for f in footers:
                            page_recovered_blocks.append({
                                "block_id": f"blk_rec_p{p_num:04d}",
                                "page_num": p_num,
                                "type": "footer",
                                "text": f,
                                "bbox": [0, 0, page.rect.width, page.rect.height]
                            })

                        if page_recovered_blocks:
                            text_blocks = [b for b in text_blocks if b.get("page_num") != p_num]
                            text_blocks.extend(page_recovered_blocks)
                            del pix, img
                            gc.collect()
                            continue

                except Exception as ocr_err:
                    logger.warning(f"Fallback OCR failed on page {p_num}: {ocr_err}")

            if not text:
                text = "[Blank Page / Image Only]"

            # ── Structured fitz re-extraction for COLLAPSED BLOB pages ───────
            # When Docling's TableFormer OOM-crashed, the page has text but no
            # structure. Use PyMuPDF's block-level dict extraction which gives
            # each physical text block with its own bbox, font size, and lines.
            # This recovers proper heading / list_item / paragraph blocks from
            # the PDF's native text layer without needing Docling.
            if p_num in collapsed_blob_pages and text:
                try:
                    dict_data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    pw = page.rect.width
                    ph = page.rect.height
                    dict_blocks = dict_data.get("blocks", [])

                    structured = []
                    for blk in dict_blocks:
                        if blk.get("type") != 0:  # 0=text, 1=image
                            continue
                        lines_text = []
                        max_fsize = 0.0
                        bbox = blk.get("bbox", [0, 0, pw, ph])
                        for ln in blk.get("lines", []):
                            for span in ln.get("spans", []):
                                span_text = span.get("text", "").strip()
                                if span_text:
                                    lines_text.append(span_text)
                                    max_fsize = max(max_fsize, span.get("size", 0))

                        full_text = " ".join(lines_text).strip()
                        if not full_text or len(full_text) < 2:
                            continue

                        x0, y0, x1, y1 = bbox
                        # Classify block type by position and font size
                        if y0 < ph * 0.06 or y0 > ph * 0.93:
                            blk_type = "footer" if y0 > ph * 0.93 else "header"
                        elif max_fsize >= 11.0 and len(full_text) < 100:
                            blk_type = "heading"
                        elif full_text.startswith("z ") or full_text.startswith("? ") or re.match(r"^\([a-d]\)\s", full_text):
                            blk_type = "list_item"
                        else:
                            blk_type = "paragraph"

                        structured.append({
                            "block_id": f"blk_dict_p{p_num:04d}",
                            "page_num": p_num,
                            "type": blk_type,
                            "text": full_text,
                            "bbox": list(bbox),
                            "is_boilerplate": blk_type in ("header", "footer"),
                            "boilerplate_type": blk_type if blk_type in ("header", "footer") else None,
                            "was_corrected": True,
                            "entities": [],
                        })

                    if len(structured) > 1:
                        # Replace the single blob with proper structured blocks
                        text_blocks = [b for b in text_blocks if b.get("page_num") != p_num]
                        text_blocks.extend(structured)
                        logger.debug(
                            f"Issue1/BlobFix: page {p_num} expanded from 1 blob "
                            f"→ {len(structured)} structured fitz dict blocks."
                        )
                        continue  # skip the flat-text fallback below
                except Exception as dict_err:
                    logger.warning(f"Structured fitz dict extraction failed on page {p_num}: {dict_err}")

            # Remove existing low-content blocks for this page BEFORE appending recovered text
            if p_num in low_content_pages and p_num not in missing_pages:
                text_blocks = [b for b in text_blocks if b.get("page_num") != p_num]
            # Also remove the collapsed blob before replacing
            if p_num in collapsed_blob_pages:
                text_blocks = [b for b in text_blocks if b.get("page_num") != p_num]


            text_blocks.append({
                "block_id": f"blk_recovery_p{p_num:04d}",   # temp ID; re-assigned later
                "page_num": p_num,
                "type": "paragraph",
                "text": text,
                "bbox": [0.0, 0.0, page.rect.width, page.rect.height]
            })

        doc.close()
    except Exception as e:
        logger.warning(f"Hybrid Fitz fallback failed: {e}")

    return text_blocks


# ── Step 3c: COLLAPSED BLOB RESTRUCTURING ────────────────────────────────────

_UPSC_LIST_PREFIX = re.compile(r"^(z |\? |\([a-d]\)\s|\d+\.\s|[•\-➢]\s)")


def _restructure_collapsed_blob_pages(
    pdf_path: Path,
    text_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Issue 1 / Fix 1 (extended): Detects pages where Docling's TableFormer model
    ran out of memory (``std::bad_alloc``) and silently collapsed the page into a
    single giant ``paragraph`` blob, losing all heading / list / caption structure.

    Detection heuristic (applied BEFORE boilerplate tagging):
        - ≤ 3 blocks on the page (any type)
        - At least one block has ``len(text) > 400`` characters

    Recovery: Re-extracts those pages via PyMuPDF ``page.get_text("dict")``
    which gives each physical text block its own bounding-box, font-size, and
    line content directly from the PDF's native text layer — no Docling required.

    Classification logic per recovered block:
        - y < 6% page height  → ``header``
        - y > 93% page height → ``footer``
        - font_size ≥ 11 pt AND text < 100 chars → ``heading``
        - text starts with UPSC bullet markers (``z ``, ``? ``, ``(a)``) → ``list_item``
        - otherwise → ``paragraph``
    """
    # Build per-page block lists
    page_blocks: Dict[int, List[Dict[str, Any]]] = {}
    for b in text_blocks:
        pg = b.get("page_num")
        if isinstance(pg, int):
            page_blocks.setdefault(pg, []).append(b)

    # Identify collapsed-blob pages
    blob_pages: set = set()
    for pg, pbs in page_blocks.items():
        if len(pbs) <= 3 and any(len(b.get("text", "")) > 400 for b in pbs):
            blob_pages.add(pg)

    if not blob_pages:
        return text_blocks

    logger.info(
        f"_restructure_collapsed_blob_pages: {len(blob_pages)} blob page(s) detected — "
        f"re-extracting via PyMuPDF dict mode."
    )

    try:
        fitz_doc = fitz.open(str(pdf_path))
        total_pages = len(fitz_doc)

        for pg in sorted(blob_pages):
            if pg < 1 or pg > total_pages:
                continue
            page = fitz_doc[pg - 1]
            pw = page.rect.width
            ph = page.rect.height

            try:
                dict_data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            except Exception as e:
                logger.warning(f"_restructure_collapsed_blob_pages: fitz dict failed on page {pg}: {e}")
                continue

            structured: List[Dict[str, Any]] = []
            blk_counter = 0
            for blk in dict_data.get("blocks", []):
                if blk.get("type") != 0:  # skip image blocks
                    continue
                lines_text: List[str] = []
                max_fsize = 0.0
                bbox = blk.get("bbox", [0.0, 0.0, pw, ph])

                for ln in blk.get("lines", []):
                    for span in ln.get("spans", []):
                        stext = span.get("text", "").strip()
                        if stext:
                            lines_text.append(stext)
                            max_fsize = max(max_fsize, span.get("size", 0.0))

                full_text = " ".join(lines_text).strip()
                if not full_text or len(full_text) < 2:
                    continue

                x0, y0, x1, y1 = bbox
                # Classify block type
                if y0 > ph * 0.93:
                    blk_type = "footer"
                    is_bp = True
                elif y0 < ph * 0.07:
                    blk_type = "header"
                    is_bp = True
                elif max_fsize >= 11.0 and len(full_text) < 120:
                    blk_type = "heading"
                    is_bp = False
                elif _UPSC_LIST_PREFIX.match(full_text):
                    blk_type = "list_item"
                    is_bp = False
                else:
                    blk_type = "paragraph"
                    is_bp = False

                blk_counter += 1
                structured.append({
                    "block_id": f"blk_dict_p{pg:04d}_{blk_counter:03d}",
                    "page_num": pg,
                    "type": blk_type,
                    "text": full_text,
                    "bbox": [round(v, 2) for v in bbox],
                    "is_boilerplate": is_bp,
                    "boilerplate_type": blk_type if is_bp else None,
                    "was_corrected": True,
                    "entities": [],
                })

            if len(structured) > 1:
                text_blocks = [b for b in text_blocks if b.get("page_num") != pg]
                text_blocks.extend(structured)
                logger.debug(
                    f"  Page {pg}: blob → {len(structured)} structured blocks (dict re-extraction)"
                )
            else:
                logger.debug(
                    f"  Page {pg}: dict re-extraction produced only {len(structured)} block(s); keeping original blob"
                )

        fitz_doc.close()

    except Exception as e:
        logger.warning(f"_restructure_collapsed_blob_pages failed: {e}")

    return text_blocks


def _deduplicate_blocks(text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    """
    Removes near-identical consecutive duplicate blocks on the same page that can arise
    when Docling produces a second linear-text pass.
    """
    if not text_blocks:
        return text_blocks

    import unicodedata

    def _fingerprint(text: str) -> str:
        """Normalise and truncate text for comparison."""
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text[:120]

    deduped: List[Dict[str, Any]] = []

    for b in text_blocks:
        text = b.get("text", "")
        fp = _fingerprint(text)
        p_num = b.get("page_num")

        # Consecutive duplicate check on same page
        if deduped:
            prev_b = deduped[-1]
            if prev_b.get("page_num") == p_num and _fingerprint(prev_b.get("text", "")) == fp:
                logger.debug(f"Dedup: removing consecutive duplicate block on page {p_num}: '{text[:60]}...'")
                continue

        deduped.append(b)

    removed = len(text_blocks) - len(deduped)
    if removed:
        logger.info(f"Dedup: removed {removed} duplicate blocks from document stream")

    return deduped



def filter_covered_text_blocks(pdf_path: Path, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Issue 6 Fix (QA Report v2):
    Filters out text blocks that are obscured/covered by white or opaque fill vector graphics
    (e.g., leftover template text covered by a white rectangle drawn over it).
    """
    if not pdf_path or not pdf_path.exists() or not text_blocks:
        return text_blocks

    try:
        fitz_doc = fitz.open(str(pdf_path))
        filtered = []
        removed_count = 0

        pages_dict: Dict[int, List[Dict[str, Any]]] = {}
        for b in text_blocks:
            pages_dict.setdefault(b.get("page_num", 1), []).append(b)

        for p_num in sorted(pages_dict.keys()):
            if p_num > len(fitz_doc):
                filtered.extend(pages_dict[p_num])
                continue

            page_obj = fitz_doc[p_num - 1]
            drawings = page_obj.get_drawings()

            white_rects = []
            page_area = page_obj.rect.width * page_obj.rect.height
            for d in drawings:
                fill = d.get("fill")
                rect = d.get("rect")
                if fill and rect and all(c > 0.9 for c in fill):
                    rect_area = abs(rect.width * rect.height)
                    # Ignore large background boxes/cards (> 5% of page area)
                    if rect_area < 0.05 * page_area:
                        white_rects.append(rect)

            for b in pages_dict[p_num]:
                bbox = b.get("bbox")
                if not bbox or len(bbox) != 4 or not white_rects:
                    filtered.append(b)
                    continue

                bl, bt, br, bb = bbox[0], bbox[1], bbox[2], bbox[3]
                ph = page_obj.rect.height

                py_y0 = ph - max(bt, bb)
                py_y1 = ph - min(bt, bb)
                b_rect = fitz.Rect(bl, py_y0, br, py_y1)
                b_area = abs(b_rect.width * b_rect.height)

                if b_area <= 0:
                    filtered.append(b)
                    continue

                is_covered = False
                for w_rect in white_rects:
                    inter = b_rect & w_rect
                    if not inter.is_empty:
                        inter_area = abs(inter.width * inter.height)
                        if (inter_area / b_area) > 0.85:
                            is_covered = True
                            break

                if is_covered:
                    logger.info(f"CoveredTextFilter: Dropping hidden block '{b.get('text', '')[:40]}' on page {p_num}")
                    removed_count += 1
                else:
                    filtered.append(b)

        fitz_doc.close()
        if removed_count:
            logger.info(f"CoveredTextFilter: Filtered out {removed_count} hidden/masked text blocks across document")
        return filtered

    except Exception as e:
        logger.warning(f"CoveredTextFilter failed: {e}")
        return text_blocks


# ── Fix 3: HEADING MISCLASSIFICATION OVERRIDE ────────────────────────────────

_HEADING_PATTERN = re.compile(
    r"^\d+(\.\d+)*\s+[A-Z]"   # e.g. "1.2 History", "3.6.1 Nagara School…"
)


def fix_heading_misclassification(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fix 3: Overrides blocks that Docling typed as ``footer`` purely by position
    when their text clearly matches a numbered section-heading pattern.

    Applies *after* :func:`tag_boilerplate_blocks` so that any legitimate
    footer blocks (bare page numbers, running titles) are already protected by
    their boilerplate flag before this function runs.

    Heuristics:
      - block["type"] must be "footer" (position-based classification)
      - text matches ``^\\d+(\\.\\d+)*\\s+[A-Z]`` (numbered heading)
      - text length < 80 characters (genuine headings are short)
      - block is NOT marked as boilerplate (real footers are already tagged)
    """
    if block.get("is_boilerplate"):
        return block
    text = block.get("text", "").strip()
    if (
        block.get("type") == "footer"
        and _HEADING_PATTERN.match(text)
        and len(text) < 80
    ):
        block["type"] = "heading"
        block["was_corrected"] = True
        logger.debug(f"Fix3/HeadingOverride: reclassified footer→heading: '{text[:60]}'")
    return block


# ── Fix 2: TOC DOT-LEADER TABLE FILTER ────────────────────────────────────────

_DOT_LEADER_RE = re.compile(r"\.{4,}")


def _is_toc_like_table(table: Dict[str, Any]) -> bool:
    """
    Returns ``True`` when a table looks like a TOC dot-leader misparse.

    Two independent signals are checked:
    - More than 50 % of rows contain a dot-leader sequence (``....``).
    - More than 40 % of rows have two or more cells with identical content
      (the common TOC mis-parse pattern where the same text is duplicated
      across fake columns).
    """
    rows = table.get("rows", [])
    if not rows:
        return False

    total = len(rows)
    dot_leader_hits = 0
    duplicate_cell_rows = 0

    for row in rows:
        row_text = " ".join(str(c) for c in row)
        if _DOT_LEADER_RE.search(row_text):
            dot_leader_hits += 1
        # Flag rows where 2+ cells are near-identical
        cells = [str(c).strip() for c in row if str(c).strip()]
        if len(cells) >= 2 and len(set(cells)) < len(cells):
            duplicate_cell_rows += 1

    return (dot_leader_hits / total > 0.5) or (duplicate_cell_rows / total > 0.4)


def filter_toc_tables(
    tables: List[Dict[str, Any]],
    text_blocks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fix 2: Removes TOC dot-leader pseudo-tables from ``tables[]`` and
    optionally re-emits their row text as ``toc`` type blocks in
    ``text_blocks[]``, skipping content that already exists there.

    Real tables (e.g. the page-27 North/South Stupa comparison) pass the
    :func:`_is_toc_like_table` check and are left completely untouched.

    Returns:
        ``(filtered_tables, updated_text_blocks)``
    """
    if not tables:
        return tables, text_blocks

    # Fingerprint existing text blocks to avoid re-adding duplicate content
    existing_fps: Set[str] = {
        re.sub(r"\s+", " ", b.get("text", "")).strip().lower()
        for b in text_blocks
    }

    filtered_tables: List[Dict[str, Any]] = []
    new_toc_blocks: List[Dict[str, Any]] = []
    toc_removed = 0

    for table in tables:
        if _is_toc_like_table(table):
            toc_removed += 1
            page_num = table.get("page_num", 1)
            # Re-emit each row's text as a toc block (no duplicates)
            for row in table.get("rows", []):
                row_text = " ".join(str(c).strip() for c in row if str(c).strip())
                if not row_text:
                    continue
                fp = re.sub(r"\s+", " ", row_text).strip().lower()
                if fp not in existing_fps:
                    new_toc_blocks.append({
                        "block_id": "",          # re-indexed after this step
                        "page_num": page_num,
                        "type": "toc",
                        "text": row_text,
                        "bbox": None,
                        "is_boilerplate": True,
                        "boilerplate_type": "toc",
                        "was_corrected": False,
                        "entities": []
                    })
                    existing_fps.add(fp)
        else:
            filtered_tables.append(table)

    if toc_removed:
        logger.info(
            f"filter_toc_tables: removed {toc_removed} TOC dot-leader pseudo-table(s); "
            f"re-emitted {len(new_toc_blocks)} unique TOC text block(s)."
        )

    return filtered_tables, text_blocks + new_toc_blocks



# ── Fix 5: FOOTER MOJIBAKE FLAGGER ──────────────────────────────────────────────

# ── Fix 6: DEGENERATE TABLE FILTER ───────────────────────────────────────────────

_GENERIC_HEADER_MARKERS: Set[str] = {
    "column_1", "column_2", "column_3", "column_4",
    "column_5", "column_6", "column_7", "column_8",
    "list?", "s/no", "s.no", "sno", "",
}


def _is_degenerate_table(table: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Fix 6: Classifies a table as degenerate (noise / misparse) using four signals.

    Returns
    -------
    (is_degenerate: bool, reason: str | None)
        ``reason`` is one of ``'empty'``, ``'single_cell'``, ``'generic_headers'``,
        or ``'sparse_rows'``; ``None`` when the table is clean.

    Rules (in priority order)
    -------------------------
    1. **empty** — ``row_count == 0`` or ``column_count == 0``.  Pure junk; safe to drop.
    2. **single_cell** — ``row_count <= 1`` and ``column_count <= 1``.  Heading or
       standalone list item misclassified as a 1×1 table.
    3. **generic_headers** — every header is a generic placeholder (``Column_1``,
       ``Column_2``, ``list?``, etc.), signalling that the table-structure model could
       not identify real column labels.  Content may still exist in ``rows``; flag for
       review rather than deleting.
    4. **sparse_rows** — more than 40 % of rows have ≤ 1 non-empty cell (possible
       row-boundary misdetection). Flag for review.
    """
    row_count = table.get("row_count", 0)
    col_count = table.get("column_count", 0)

    # 1. Empty
    if row_count == 0 or col_count == 0:
        return True, "empty"

    # 2. Single-cell (1×1 or 1×0 etc.)
    if row_count <= 1 and col_count <= 1:
        return True, "single_cell"

    # 3. Generic placeholder headers
    headers = table.get("headers", [])
    if headers and all(str(h).strip().lower() in _GENERIC_HEADER_MARKERS for h in headers):
        return True, "generic_headers"

    # 4. Sparse rows
    rows = table.get("rows", [])
    if rows:
        sparse = sum(
            1 for r in rows
            if sum(1 for c in r if str(c).strip()) <= 1
        )
        if sparse / len(rows) > 0.4:
            return True, "sparse_rows"

    return False, None


def filter_degenerate_tables(
    tables: List[Dict[str, Any]],
    text_blocks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fix 6: Removes or flags degenerate entries from ``tables[]``.

    - ``empty`` and ``single_cell`` tables are **removed** and their text is
      re-emitted as ``list_item`` blocks in ``text_blocks[]`` (unless already present).
    - ``generic_headers`` and ``sparse_rows`` tables are **kept** but annotated with
      ``needs_review: True`` so auditors can spot-check them.

    Returns
    -------
    ``(filtered_tables, updated_text_blocks)``
    """
    if not tables:
        return tables, text_blocks

    existing_fps: Set[str] = {
        re.sub(r"\s+", " ", b.get("text", "")).strip().lower()
        for b in text_blocks
    }

    filtered_tables: List[Dict[str, Any]] = []
    recovered_blocks: List[Dict[str, Any]] = []
    stats = {"removed_empty": 0, "removed_single_cell": 0, "flagged": 0}

    for table in tables:
        is_degen, reason = _is_degenerate_table(table)

        if not is_degen:
            filtered_tables.append(table)
            continue

        if reason in ("empty", "single_cell"):
            # Drop table, try to rescue its text content
            cat = "removed_empty" if reason == "empty" else "removed_single_cell"
            stats[cat] += 1
            page_num = table.get("page_num", 1)
            for row in table.get("rows", []):
                cell_texts = [str(c).strip() for c in row if str(c).strip()]
                text = " ".join(cell_texts)
                if not text:
                    continue
                fp = re.sub(r"\s+", " ", text).strip().lower()
                if fp not in existing_fps:
                    recovered_blocks.append({
                        "block_id": "",
                        "page_num": page_num,
                        "type": "list_item",
                        "text": text,
                        "bbox": None,
                        "is_boilerplate": False,
                        "boilerplate_type": None,
                        "was_corrected": True,
                        "entities": [],
                    })
                    existing_fps.add(fp)
        else:
            # generic_headers or sparse_rows — keep but flag
            table["needs_review"] = True
            filtered_tables.append(table)
            stats["flagged"] += 1

    removed = stats["removed_empty"] + stats["removed_single_cell"]
    if removed or stats["flagged"]:
        logger.info(
            f"filter_degenerate_tables: removed {removed} degenerate table(s) "
            f"({stats['removed_empty']} empty, {stats['removed_single_cell']} single-cell); "
            f"flagged {stats['flagged']} as needs_review=True; "
            f"recovered {len(recovered_blocks)} text block(s)."
        )

    return filtered_tables, text_blocks + recovered_blocks



def _flag_mojibake_blocks(
    text_blocks: List[Dict[str, Any]],
    garbage_ratio_threshold: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Fix 5: Flags boilerplate blocks whose text is predominantly garbled non-ASCII
    bytes (a font cmap/encoding mismatch common in stamped watermark PDFs).

    Sets ``encoding_error: True`` on affected blocks so auditors can distinguish
    mojibake from genuinely blank footers.  Content is **never rewritten** —
    this is a metadata-only annotation.

    Only operates on blocks already marked ``is_boilerplate: True`` because the
    fix guide rates this low-priority and explicitly limits it to watermark junk.

    Args:
        text_blocks:              Full document block list.
        garbage_ratio_threshold:  Fraction of characters that must be
                                  non-printable / control bytes before the block
                                  is flagged (default 30 %).

    Returns:
        Block list with ``encoding_error: True`` added to affected blocks.
    """
    flagged = 0
    for block in text_blocks:
        if not block.get("is_boilerplate"):
            continue
        text = block.get("text", "")
        if not text:
            continue
        # Count characters that are non-printable, replacement char U+FFFD (), or non-ASCII
        garbage = sum(
            1 for ch in text
            if not ch.isprintable() or ch == "\ufffd" or ord(ch) >= 0x80
        )
        ratio = garbage / len(text)
        if ratio >= garbage_ratio_threshold:
            block["encoding_error"] = True
            flagged += 1
        else:
            block.setdefault("encoding_error", False)

    if flagged:
        logger.info(
            f"_flag_mojibake_blocks: flagged {flagged} boilerplate block(s) "
            f"with encoding_error=True (>{garbage_ratio_threshold:.0%} garbage bytes)."
        )
    return text_blocks


# ── Fix 7: PYQ BOILERPLATE MISCLASSIFICATION RESCUE ──────────────────────────

_PYQ_MARKERS = re.compile(
    r"""^(
        Q[\.\t\s]                      # "Q." / "Q\t" UPSC-style question prefix
        | PREVIOUS\ YEAR\ QUESTION     # Box banner header
        | With\ reference              # Common UPSC question opener
        | Consider\ the\ following     # Common UPSC question opener
        | Which\ (of|one|among)        # Common UPSC question opener
        | How\ many                    # Quantitative question opener
        | What\ (is|are|was|were)      # Factual question opener
        | \([a-d]\)\s                  # MCQ option (a)/(b)/(c)/(d)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def fix_pyq_misclassification(
    text_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fix 7: Rescues UPSC Practice Question (PYQ) blocks that were silently
    dropped by the boilerplate filter because they appeared in a footer-like
    position (low on the page, near the pink PYQ banner).

    These blocks are HIGH-VALUE content — they are the exam practice questions
    themselves (not decorative page furniture) — so they should NEVER be
    excluded from downstream chunking/embedding.

    Actions
    -------
    - Sets ``type`` to ``'pyq_question'`` (dedicated schema type for downstream
      retrieval — e.g. flashcard / practice-question feature).
    - Clears ``is_boilerplate`` (ensures they are NOT skipped by boilerplate
      filters).
    - Sets ``was_corrected: True``.

    Only applies to blocks that:
    1. Were already typed ``footer`` AND ``is_boilerplate: True``.
    2. Whose text matches :data:`_PYQ_MARKERS`.
    """
    rescued = 0
    for block in text_blocks:
        if not block.get("is_boilerplate"):
            continue
        if block.get("type") != "footer":
            continue
        text = block.get("text", "").strip()
        if not text:
            continue
        if _PYQ_MARKERS.match(text):
            block["type"] = "pyq_question"
            block["is_boilerplate"] = False
            block["was_corrected"] = True
            rescued += 1
            logger.debug(f"Fix7/PYQRescue: boilerplate footer → pyq_question: '{text[:60]}'")

    if rescued:
        logger.info(
            f"fix_pyq_misclassification: rescued {rescued} PYQ block(s) "
            f"from boilerplate footer → pyq_question."
        )
    return text_blocks


# ── Fix 8: BLANK-PAGE / TABLE CROSS-CHECK ────────────────────────────────────

def fix_blank_page_flag(
    text_blocks: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fix 8: Removes incorrect ``blank_page`` markers from pages that actually
    contain real tables in ``tables[]``.

    Root cause: The blank-page heuristic only checks ``text_blocks[]`` and does
    not look at ``tables[]``.  Pages whose entire content is a data table (e.g.
    Indus Valley sites list, Protected Area sites table) end up with a
    ``blank_page`` text block even though their content is present and correct.

    Any downstream consumer that gatekeeps on ``text_blocks`` alone will
    incorrectly skip those pages.

    Actions
    -------
    - Builds a set of page numbers that have at least one table entry.
    - Removes ``blank_page`` typed blocks whose ``page_num`` is in that set.
    - Returns the cleaned block list.
    """
    pages_with_tables: Set[int] = {
        t.get("page_num") for t in tables if t.get("page_num") is not None
    }

    cleaned: List[Dict[str, Any]] = []
    removed = 0
    for block in text_blocks:
        if (
            block.get("type") == "blank_page"
            and block.get("page_num") in pages_with_tables
        ):
            removed += 1
            logger.debug(
                f"Fix8/BlankPageCrossCheck: removed spurious blank_page on "
                f"page {block.get('page_num')} (page has {sum(1 for t in tables if t.get('page_num') == block.get('page_num'))} table(s))"
            )
        else:
            cleaned.append(block)

    if removed:
        logger.info(
            f"fix_blank_page_flag: removed {removed} spurious blank_page block(s) "
            f"from pages that have real table content."
        )
    return cleaned


# ── 4. PAGE & EMBEDDED IMAGE EXPORTER ─────────────────────────────────────────

def save_page_images(doc: Any, output_dir: Path, pdf_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Saves page rendered images and extracts embedded PDF images/figures into output_dir.

    Page renders
    ------------
    First attempts to use Docling's built-in page images (only available when
    ``generate_page_images=True`` was set in the pipeline options).
    When those are absent (the common case with ``generate_page_images=False``),
    falls back to rendering via PyMuPDF at 1× scale (72 DPI).  This resolution
    is sufficient for background-color sampling in Fix 4 (callout detector) while
    keeping per-page file sizes small (~30–80 KB PNG).
    """
    image_meta = []
    images_dir = output_dir / "page_images"

    # 4a. Docling Page Rendered Images (only available if generate_page_images=True)
    if hasattr(doc, "pages") and doc.pages:
        for page_no, page in doc.pages.items():
            if hasattr(page, "image") and page.image:
                try:
                    images_dir.mkdir(parents=True, exist_ok=True)
                    img_filename = f"page_{page_no:03d}.png"
                    img_path = images_dir / img_filename
                    page.image.pil_image.save(str(img_path), "PNG")

                    image_meta.append({
                        "page_num": page_no,
                        "type": "page_render",
                        "filename": img_filename,
                        "path": str(img_path.relative_to(output_dir.parent))
                    })
                except Exception as e:
                    logger.warning(f"Failed to save page image for page {page_no}: {e}")

    # 4a-fallback. PyMuPDF page render fallback
    # When Docling page images are unavailable (generate_page_images=False), render
    # all pages with fitz at 1x (72 DPI).  This is fast, memory-efficient, and
    # produces files small enough to store alongside the JSON output.
    docling_renders = sum(1 for m in image_meta if m.get("type") == "page_render")
    if docling_renders == 0 and pdf_path and pdf_path.exists():
        try:
            fitz_doc = fitz.open(str(pdf_path))
            images_dir.mkdir(parents=True, exist_ok=True)
            mat = fitz.Matrix(1.0, 1.0)  # 1x = 72 DPI — sufficient for color sampling
            for page_idx in range(len(fitz_doc)):
                try:
                    page = fitz_doc[page_idx]
                    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                    img_filename = f"page_{page_idx + 1:03d}.png"
                    img_path = images_dir / img_filename
                    pix.save(str(img_path))
                    image_meta.append({
                        "page_num": page_idx + 1,
                        "type": "page_render",
                        "filename": img_filename,
                        "path": str(img_path.relative_to(output_dir.parent))
                    })
                except Exception as page_err:
                    logger.debug(f"fitz render failed for page {page_idx + 1}: {page_err}")
            fitz_doc.close()
            logger.info(
                f"save_page_images: rendered {len([m for m in image_meta if m.get('type') == 'page_render'])} "
                f"page images via PyMuPDF fallback (72 DPI)."
            )
        except Exception as fitz_err:
            logger.warning(f"PyMuPDF page render fallback failed: {fitz_err}")

    # 4b. PyMuPDF Embedded Image Figure Extraction
    if pdf_path and pdf_path.exists():
        try:
            fitz_doc = fitz.open(str(pdf_path))
            figure_counter = 1
            figures_dir = output_dir / "extracted_figures"
            figures_dir.mkdir(parents=True, exist_ok=True)

            for page_idx in range(len(fitz_doc)):
                page = fitz_doc[page_idx]
                image_list = page.get_images(full=True)
                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]
                    base_image = fitz_doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    # Issue 6 fix: skip micro-tile fragments (< 60x60 px or < 3KB) from sliced maps
                    if (width > 0 and width < 60) or (height > 0 and height < 60) or len(image_bytes) < 3000:
                        continue

                    fig_filename = f"fig_p{page_idx+1:03d}_{figure_counter:02d}.{image_ext}"
                    fig_path = figures_dir / fig_filename
                    with open(fig_path, "wb") as f:
                        f.write(image_bytes)

                    image_meta.append({
                        "page_num": page_idx + 1,
                        "type": "embedded_figure",
                        "filename": fig_filename,
                        "path": str(fig_path.relative_to(output_dir.parent))
                    })
                    figure_counter += 1
            fitz_doc.close()
        except Exception as img_err:
            logger.warning(f"PyMuPDF embedded image extraction warning: {img_err}")

    return image_meta



# ── 5. PRIMARY EXTRACTION FUNCTION ───────────────────────────────────────────

def extract_document(
    pdf_path: Path,
    output_dir: Path,
    converter: Optional[Any] = None
) -> Tuple[Any, Dict[str, Any]]:
    """
    Full extraction pipeline for a single PDF file:
      Step 0: Auto PDF type detection (SCANNED vs DIGITAL)
      Step 1: Converts PDF via Docling
      Step 2: Incomplete coverage retry fallback
      Step 3: Hybrid Fitz + Per-Page RapidOCR fallback (Guarantees 100% Page Coverage)
      Step 4: Post-processing pipeline (Block Cleaner, Boilerplate, Text Corrector, NER)

    Returns:
        (docling_doc_object, processed_data_dict)
    """
    logger.info(f"Extracting document: {pdf_path.name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Auto PDF Type Detection
    is_scanned = is_scanned_pdf(pdf_path)

    if converter is None:
        opts = DOCLING_PIPELINE_OPTIONS
        converter = get_docling_converter(
            do_ocr=is_scanned or opts.get("do_ocr", False),
            do_table_structure=opts.get("do_table_structure", False),
            generate_page_images=opts.get("generate_page_images", False)
        )

    # Step 1: Docling Conversion (Page-by-page to limit memory usage and prevent OOM/std::bad_alloc)
    text_blocks, tables = [], []
    doc = None
    total_pdf_pages = 0
    page_widths = {}
    
    try:
        pdf_doc = fitz.open(str(pdf_path))
        total_pdf_pages = len(pdf_doc)
        page_widths = {
            i + 1: pdf_doc[i].rect.width for i in range(total_pdf_pages)
        }
        
        # We will create temporary single-page PDFs in the output directory
        temp_dir = output_dir / "temp_pages"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        for page_idx in range(total_pdf_pages):
            p_num = page_idx + 1
            temp_pdf_path = temp_dir / f"page_{p_num:04d}.pdf"
            try:
                # Save single page to temp PDF
                temp_doc = fitz.open()
                temp_doc.insert_pdf(pdf_doc, from_page=page_idx, to_page=page_idx)
                temp_doc.save(str(temp_pdf_path))
                temp_doc.close()
                
                # Convert single page
                conv_result = converter.convert(str(temp_pdf_path))
                p_doc = conv_result.document
                p_text_blocks, p_tables = parse_docling_elements(p_doc)
                
                # Re-map page numbers to actual p_num
                for b in p_text_blocks:
                    b["page_num"] = p_num
                for t in p_tables:
                    t["page_num"] = p_num
                    
                text_blocks.extend(p_text_blocks)
                tables.extend(p_tables)
                
            except Exception as page_exc:
                logger.warning(
                    f"Docling page-by-page conversion failed for page {p_num}: {page_exc}. "
                    f"Will be recovered by Hybrid Fitz Fallback."
                )
            finally:
                # Clean up temp page file
                if temp_pdf_path.exists():
                    try:
                        temp_pdf_path.unlink()
                    except Exception:
                        pass
                gc.collect()
                
        # Clean up temp directory
        try:
            temp_dir.rmdir()
        except Exception:
            pass
            
        pdf_doc.close()
    except Exception as exc:
        logger.warning(
            f"Docling page-by-page conversion initialization failed for {pdf_path.name}: {exc}. "
            f"Falling back to 100% PyMuPDF / Fitz extraction."
        )
        text_blocks, tables = [], []

    covered_pages = {b.get("page_num") for b in text_blocks if isinstance(b.get("page_num"), int)}
    covered_pages.update({t.get("page_num") for t in tables if isinstance(t.get("page_num"), int)})

    if total_pdf_pages > 0 and len(covered_pages) < total_pdf_pages:
        logger.warning(
            f"Incomplete page coverage ({len(covered_pages)}/{total_pdf_pages} pages) for {pdf_path.name}. "
            f"Missing pages will be recovered by Hybrid Fitz Fallback (Step 3)."
        )

    # Step 3: Hybrid Fitz + Per-Page RapidOCR Fallback (Guarantees 100% Page Coverage)
    text_blocks = _fill_missing_pages_via_fitz(pdf_path, text_blocks)
    logger.info(f"Parsed {len(text_blocks)} text blocks, {len(tables)} tables")

    # Step 3b: Global deduplication — removes duplicate block sequences that can
    # appear when Docling emits both a layout pass and a linear text pass.
    text_blocks = _deduplicate_blocks(text_blocks)

    # Step 3c: Collapsed Blob Restructuring (Issue 1 / Fix 1 extension)
    # Detects pages where Docling's TableFormer ran out of RAM (std::bad_alloc)
    # and silently dumped the entire page as one giant paragraph blob.
    # Re-extracts those pages using PyMuPDF's get_text("dict") which provides
    # line-level block structure directly from the PDF's native text layer.
    text_blocks = _restructure_collapsed_blob_pages(pdf_path, text_blocks)


    # 4a. 7-Pass Block Cleaner (Watermarks, Glyphs, Stylized Headings, Reading Order)
    text_blocks = clean_extracted_blocks(text_blocks)

    # 4b. Tag Boilerplate
    text_blocks = tag_boilerplate_blocks(text_blocks)

    # 4b.5. Fix 3: Heading Misclassification Override (footer → heading)
    # Must run after boilerplate tagging so real footer boilerplate is already
    # protected by is_boilerplate=True before this pattern check fires.
    text_blocks = [fix_heading_misclassification(b) for b in text_blocks]

    # 4c. Fix 1: Column-aware Reading Order (left column → right column, per page)
    # Must run after Fix 3 so the corrected block types are in place, and before
    # text correction so context-dependent logic sees the right order.
    text_blocks = reorder_all_pages(text_blocks, page_widths)

    # 4d. Text Correction
    text_blocks = correct_extracted_blocks(text_blocks)

    # 4d. NER Enrichment
    text_blocks = enrich_blocks_with_ner(text_blocks)

    # 4e. Filter out covered/hidden text blocks (Issue 6 fix in QA Report v2)
    text_blocks = filter_covered_text_blocks(pdf_path, text_blocks)

    # 4f. Fix 2: TOC Dot-Leader Table Filter
    # Removes pseudo-tables that are really TOC lines and optionally re-emits
    # their content as toc-type text blocks (duplicate-safe).
    tables, text_blocks = filter_toc_tables(tables, text_blocks)

    # 4f-ii. Fix 6: Degenerate Table Filter
    # Runs directly after Fix 2 since both operate on tables[].
    # - Removes empty (row_count=0) and single-cell (1×1) tables, re-emitting
    #   their text content as list_item blocks so no content is silently lost.
    # - Flags generic-header and sparse-row tables with needs_review=True
    #   rather than deleting them, preserving potentially valid data for human audit.
    tables, text_blocks = filter_degenerate_tables(tables, text_blocks)

    # 4f-iii. Post-process extracted tables to fix column wrap/misalignment (Issue 2)
    # and duplicate headers (Issue 6)
    from extraction.table_service import _postprocess_table
    tables = [_postprocess_table(t) for t in tables]

    # 4g. Re-index block_ids contiguously after all additions/removals (blk_0001 → blk_N)
    for idx, b in enumerate(text_blocks, start=1):
        b["block_id"] = f"blk_{idx:04d}"


    # Step 5: Save page images and embedded figure assets
    # Must run before Fix 4 so page renders are available for color sampling.
    page_images = save_page_images(doc, output_dir, pdf_path=pdf_path)

    # 4h. Fix 4: Colored Callout Box Detection
    # Samples the rendered page image behind each block's bbox to detect non-white
    # background fills (pink/yellow/blue callout boxes).  No-ops gracefully when
    # page images are unavailable (generate_page_images=False) or Pillow is missing.
    text_blocks = tag_callout_blocks(
        text_blocks, page_images, output_dir, pdf_path=pdf_path
    )

    # 4i. Fix 5: Footer Mojibake Flagger
    # Flags boilerplate blocks with garbled non-ASCII bytes as encoding_error=True.
    # Metadata-only — content is never rewritten.
    text_blocks = _flag_mojibake_blocks(text_blocks)

    # 4j. Fix 7: PYQ Boilerplate Rescue
    # Rescues UPSC Practice Question (PYQ) blocks that were silently dropped as
    # boilerplate footers. These are exam questions — highest-value content — so
    # they must never be excluded from downstream chunking/embedding.
    text_blocks = fix_pyq_misclassification(text_blocks)

    # 4k. Fix 8: Blank-Page / Table Cross-Check
    # Removes spurious blank_page markers from pages that actually contain tables.
    # Prevents downstream consumers from incorrectly treating table-only pages as empty.
    text_blocks = fix_blank_page_flag(text_blocks, tables)

    # Final re-index after all fixes (block IDs must stay contiguous)
    for idx, b in enumerate(text_blocks, start=1):
        b["block_id"] = f"blk_{idx:04d}"

    extracted_data = {
        "text_blocks": text_blocks,
        "tables": tables,
        "page_images": page_images,
        "block_count": len(text_blocks),
        "table_count": len(tables)
    }

    return doc, extracted_data
