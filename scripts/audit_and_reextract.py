"""
audit_and_reextract.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive audit & re-extraction tool for all ingested PDF documents.

What this script does:
1. LINE-BY-LINE AUDIT:
   - Scans every document in PostgreSQL / uploads directory.
   - Opens the actual PDF with PyMuPDF to count exact total pages (1..N).
   - Reads the extracted JSON (data/extracted/<doc_id>.json).
   - Checks every single page line-by-line to verify if it was extracted.
   - Identifies:
       • Completely MISSED pages (page has text in PDF, but 0 blocks in JSON)
       • EMPTY/BLANK pages (page has no text in PDF or JSON)
       • PARTIAL pages (extracted text is suspiciously short compared to PDF)

2. SMART RE-EXTRACTION:
   - Re-extracts all missed/partial pages using high-fidelity PyMuPDF blocks.
   - Formats them into standard structured text_blocks.
   - Re-inserts them into data/extracted/<doc_id>.json in correct page order.

3. PIPELINE RE-SYNC:
   - Re-runs Preprocessing & Chunking (data/preprocessed/<doc_id>_preprocessed.json).
   - Re-runs BGE Embedding on the updated chunks.
   - Upserts the new vectors into Qdrant vector collections.
   - Updates PostgreSQL status to 'ingested'.

Usage:
  # 1. Audit all documents (dry-run, no changes):
  python audit_and_reextract.py --audit-only

  # 2. Audit and automatically re-extract all missed pages across all PDFs:
  python audit_and_reextract.py --reextract

  # 3. Check / re-extract a specific document by filename or ID:
  python audit_and_reextract.py --file 290-10-22-0-57-21.pdf --reextract

  # 4. Filter by classification (Anthropology / History):
  python audit_and_reextract.py --classification Anthropology --reextract
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Enable UTF-8 console output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import fitz  # PyMuPDF
from sqlalchemy import select
from app.database.session import SessionLocal
from app.database.models import Document
from app.core.config import EXTRACTED_DIR, PREPROCESSED_DIR, UPLOAD_DIR
from app.services.preprocessing_service import run_preprocessing
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AuditReExtract")


def audit_single_document(
    doc_id: str,
    pdf_path: Path,
    extracted_json_path: Path,
    min_chars_threshold: int = 30,
) -> Dict[str, Any]:
    """
    Perform a strict, page-by-page audit comparing actual PDF pages
    against the extracted JSON blocks.
    """
    report = {
        "doc_id": doc_id,
        "pdf_path": str(pdf_path),
        "pdf_exists": pdf_path.exists(),
        "json_exists": extracted_json_path.exists(),
        "total_pdf_pages": 0,
        "extracted_pages_count": 0,
        "missing_pages": [],       # Pages that have text in PDF but are missing in JSON
        "blank_pdf_pages": [],     # Pages genuinely blank in the PDF
        "partial_pages": [],       # Pages with very low extracted text compared to PDF
        "page_details": {},        # {page_num: {"pdf_lines": int, "json_blocks": int, "status": str}}
        "is_complete": True,
    }

    if not pdf_path.exists():
        report["is_complete"] = False
        report["error"] = f"PDF file not found at: {pdf_path}"
        return report

    if not extracted_json_path.exists():
        report["is_complete"] = False
        report["error"] = f"Extracted JSON not found at: {extracted_json_path}"
        return report

    # 1. Inspect original PDF
    try:
        pdf_doc = fitz.open(str(pdf_path))
        report["total_pdf_pages"] = len(pdf_doc)
    except Exception as e:
        report["is_complete"] = False
        report["error"] = f"Failed to open PDF: {e}"
        return report

    # 2. Inspect Extracted JSON
    try:
        with open(extracted_json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        report["is_complete"] = False
        report["error"] = f"Failed to read extracted JSON: {e}"
        pdf_doc.close()
        return report

    text_blocks = json_data.get("text_blocks", [])

    # Group extracted blocks and char counts by page_num (1-indexed)
    extracted_by_page: Dict[int, List[Dict[str, Any]]] = {}
    extracted_chars_by_page: Dict[int, int] = {}
    extracted_lines_by_page: Dict[int, int] = {}

    for b in text_blocks:
        p = b.get("page_num")
        if p is None:
            continue
        extracted_by_page.setdefault(p, []).append(b)
        txt = b.get("text", "") or ""
        extracted_chars_by_page[p] = extracted_chars_by_page.get(p, 0) + len(txt)
        extracted_lines_by_page[p] = extracted_lines_by_page.get(p, 0) + len(txt.splitlines())

    report["extracted_pages_count"] = len(extracted_by_page)

    # 3. Check every single page 1..N
    for page_idx in range(len(pdf_doc)):
        page_num = page_idx + 1
        page = pdf_doc[page_idx]
        pdf_text = page.get_text("text").strip()
        pdf_char_count = len(pdf_text)
        pdf_line_count = len(pdf_text.splitlines()) if pdf_text else 0

        json_blocks = extracted_by_page.get(page_num, [])
        json_char_count = extracted_chars_by_page.get(page_num, 0)
        json_line_count = extracted_lines_by_page.get(page_num, 0)

        # Analysis
        if pdf_char_count == 0:
            # Genuinely empty / blank / image-only page in PDF
            page_status = "BLANK_IN_PDF"
            report["blank_pdf_pages"].append(page_num)
        elif len(json_blocks) == 0:
            # PDF has text, but JSON has 0 blocks -> MISSED!
            page_status = "MISSED"
            report["missing_pages"].append(page_num)
            report["is_complete"] = False
        elif json_char_count < min_chars_threshold and pdf_char_count > min_chars_threshold * 2:
            # PDF has significant text, but JSON only got a few characters -> PARTIAL!
            page_status = "PARTIAL"
            report["partial_pages"].append(page_num)
            report["is_complete"] = False
        else:
            page_status = "OK"

        report["page_details"][page_num] = {
            "pdf_chars": pdf_char_count,
            "pdf_lines": pdf_line_count,
            "json_blocks": len(json_blocks),
            "json_chars": json_char_count,
            "json_lines": json_line_count,
            "status": page_status,
        }

    pdf_doc.close()
    return report


def reextract_missed_pages(
    pdf_path: Path,
    extracted_json_path: Path,
    missing_pages: List[int],
    partial_pages: List[int],
) -> Tuple[bool, int, str]:
    """
    Extracts missed or partial pages from the PDF using PyMuPDF and patches
    them into the extracted JSON in correct sorted order.
    """
    pages_to_extract = sorted(list(set(missing_pages + partial_pages)))
    if not pages_to_extract:
        return True, 0, "No pages to re-extract."

    try:
        pdf_doc = fitz.open(str(pdf_path))
    except Exception as e:
        return False, 0, f"Failed to open PDF: {e}"

    try:
        with open(extracted_json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        pdf_doc.close()
        return False, 0, f"Failed to load JSON: {e}"

    existing_blocks = json_data.get("text_blocks", [])

    # If partial pages are being re-extracted, remove their previous incomplete blocks
    if partial_pages:
        existing_blocks = [b for b in existing_blocks if b.get("page_num") not in partial_pages]

    new_blocks = []
    total_reextracted_chars = 0

    for page_num in pages_to_extract:
        page_idx = page_num - 1
        if page_idx < 0 or page_idx >= len(pdf_doc):
            continue

        page = pdf_doc[page_idx]
        # Get raw text blocks: (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")

        for b_idx, blk in enumerate(blocks):
            if len(blk) < 5:
                continue
            x0, y0, x1, y1, blk_text = blk[0], blk[1], blk[2], blk[3], blk[4]
            blk_text = blk_text.strip()
            if not blk_text:
                continue

            # Determine type (heading vs paragraph vs list)
            blk_type = "paragraph"
            lines = blk_text.splitlines()
            if len(lines) == 1 and len(blk_text) < 80 and not blk_text.endswith("."):
                blk_type = "heading"
            elif any(blk_text.strip().startswith(prefix) for prefix in ["•", "-", "*", "1.", "2.", "3.", "4.", "5.", "(a)", "(b)", "(i)"]):
                blk_type = "list_item"

            block_obj = {
                "block_id": f"blk_re_p{page_num}_{b_idx:04d}",
                "page_num": page_num,
                "type": blk_type,
                "text": blk_text,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "is_boilerplate": False,
                "boilerplate_type": None,
                "was_corrected": False,
                "entities": [],
            }
            new_blocks.append(block_obj)
            total_reextracted_chars += len(blk_text)

    pdf_doc.close()

    if not new_blocks:
        return True, 0, "No new text was found on the target pages (they might be pure images/diagrams)."

    # Merge and sort all blocks by (page_num, y0 bbox)
    all_blocks = existing_blocks + new_blocks
    all_blocks.sort(key=lambda b: (b.get("page_num", 0), (b.get("bbox", [0, 0])[1] if b.get("bbox") else 0)))

    # Update summary metadata
    json_data["text_blocks"] = all_blocks
    if "extraction_summary" in json_data:
        json_data["extraction_summary"]["total_blocks"] = len(all_blocks)
    if "document_metadata" in json_data:
        json_data["document_metadata"]["page_count"] = max(
            json_data["document_metadata"].get("page_count", 0),
            max(pages_to_extract, default=0)
        )

    # Save updated JSON
    try:
        with open(extracted_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return False, 0, f"Failed to save updated JSON: {e}"

    return True, len(new_blocks), f"Successfully re-extracted {len(pages_to_extract)} pages ({len(new_blocks)} blocks, {total_reextracted_chars} chars)."


def resync_pipeline(doc_id: str, classification: str, extracted_json_path: Path) -> Tuple[bool, str]:
    """
    Re-runs preprocessing, embedding, and Qdrant upsert for the document.
    """
    logger.info(f"[{doc_id}] Step 1: Re-running Preprocessing...")
    ok_pre, pre_path, err_pre = run_preprocessing(doc_id, extracted_json_path)
    if not ok_pre or not pre_path:
        return False, f"Preprocessing failed: {err_pre}"

    logger.info(f"[{doc_id}] Step 2: Re-running BGE Embeddings...")
    ok_emb, emb_chunks, err_emb = run_embedding(pre_path)
    if not ok_emb or not emb_chunks:
        return False, f"Embedding failed: {err_emb}"

    logger.info(f"[{doc_id}] Step 3: Upserting {len(emb_chunks)} vectors to Qdrant ({classification})...")
    ok_qdr, err_qdr = run_qdrant_upsert(doc_id, classification, emb_chunks)
    if not ok_qdr:
        return False, f"Qdrant upsert failed: {err_qdr}"

    return True, f"Successfully re-indexed {len(emb_chunks)} chunks in Qdrant."


def main():
    parser = argparse.ArgumentParser(description="Audit and re-extract missing pages from ingested PDFs.")
    parser.add_argument("--audit-only", action="store_true", help="Only audit documents, do not modify files or DB.")
    parser.add_argument("--reextract", action="store_true", help="Automatically re-extract missing pages and update Qdrant.")
    parser.add_argument("--file", type=str, help="Target specific filename or document UUID.")
    parser.add_argument("--classification", type=str, choices=["Anthropology", "History"], help="Filter by classification.")
    parser.add_argument("--min-chars", type=int, default=30, help="Minimum characters threshold for a page.")
    args = parser.parse_args()

    reextract_mode = args.reextract or (not args.audit_only and False)

    print("\n" + "=" * 80)
    print("🔍 UPSC AI RAG — PDF PAGE AUDIT & RE-EXTRACTION SYSTEM")
    print("=" * 80)
    print(f"Mode: {'🛠️ RE-EXTRACT & SYNC TO QDRANT' if reextract_mode else '📊 AUDIT ONLY (Read-Only)'}")
    print(f"Min Characters Threshold: {args.min_chars}")
    if args.file:
        print(f"Filter File: {args.file}")
    if args.classification:
        print(f"Filter Classification: {args.classification}")
    print("=" * 80 + "\n")

    # Fetch documents from PostgreSQL
    with SessionLocal() as db:
        query = select(Document).order_by(Document.created_at.desc())
        if args.classification:
            query = query.where(Document.classification == args.classification)
        documents = db.execute(query).scalars().all()

    if not documents:
        print("❌ No documents found in database.")
        return

    # Filter by specific file if requested
    if args.file:
        documents = [d for d in documents if args.file.lower() in d.original_filename.lower() or args.file == d.id]
        if not documents:
            print(f"❌ No document matched '{args.file}'.")
            return

    print(f"Found {len(documents)} document(s) to audit.\n")

    total_audited = 0
    total_complete = 0
    total_with_missing_pages = 0
    total_pages_reextracted = 0

    for idx, doc in enumerate(documents, start=1):
        pdf_p = Path(doc.file_path)
        json_p = Path(doc.extracted_json_path) if doc.extracted_json_path else (EXTRACTED_DIR / f"{doc.id}.json")

        report = audit_single_document(
            doc_id=doc.id,
            pdf_path=pdf_p,
            extracted_json_path=json_p,
            min_chars_threshold=args.min_chars,
        )

        total_audited += 1
        pdf_pages = report["total_pdf_pages"]
        ext_pages = report["extracted_pages_count"]
        missing = report["missing_pages"]
        partial = report["partial_pages"]
        blank = report["blank_pdf_pages"]

        if report.get("error"):
            print(f"[{idx}/{len(documents)}] ❌ {doc.original_filename}")
            print(f"    Error: {report['error']}\n")
            continue

        if report["is_complete"]:
            total_complete += 1
            status_icon = "✅"
            status_text = "COMPLETE (All pages extracted)"
        else:
            total_with_missing_pages += 1
            status_icon = "⚠️"
            status_text = f"INCOMPLETE ({len(missing)} missed, {len(partial)} partial)"

        print(f"[{idx}/{len(documents)}] {status_icon} {doc.original_filename} ({doc.classification})")
        print(f"    UUID: {doc.id}")
        print(f"    Pages: {ext_pages}/{pdf_pages} extracted | Blank in PDF: {len(blank)} | Status: {status_text}")

        if missing:
            print(f"    ❌ Missed Pages (have text in PDF, 0 in JSON): {missing}")
        if partial:
            print(f"    ⚠️  Partial Pages (suspiciously short text): {partial}")

        # If reextract is requested and there are missing or partial pages
        if reextract_mode and (missing or partial):
            print(f"    🔄 Re-extracting missed pages: {missing + partial}...")
            ok_re, num_blocks, msg_re = reextract_missed_pages(pdf_p, json_p, missing, partial)
            if ok_re and num_blocks > 0:
                print(f"    ✓ {msg_re}")
                # Resync preprocessing, embedding, and Qdrant
                ok_sync, msg_sync = resync_pipeline(doc.id, doc.classification, json_p)
                if ok_sync:
                    print(f"    ✓ {msg_sync}")
                    total_pages_reextracted += len(missing + partial)
                else:
                    print(f"    ❌ Pipeline resync failed: {msg_sync}")
            else:
                print(f"    ⚠️  {msg_re}")

        print("-" * 80)

    print("\n" + "=" * 80)
    print("📊 FINAL AUDIT & RE-EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total Documents Audited:          {total_audited}")
    print(f"100% Complete Documents:         {total_complete}")
    print(f"Documents with Missing Pages:     {total_with_missing_pages}")
    if reextract_mode:
        print(f"Total Missing Pages Re-extracted: {total_pages_reextracted}")
    else:
        print(f"Tip: Run with --reextract to automatically extract all missed pages and sync to Qdrant!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
