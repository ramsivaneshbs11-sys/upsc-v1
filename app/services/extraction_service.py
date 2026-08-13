"""
extraction_service.py
───────────────────────
Bridges the FastAPI endpoint with the existing Docling extraction pipeline
located in daily/extraction/.

Sequential steps performed inside run_extraction():
  1. validate_pdf    – checks file integrity and returns basic metadata
  2. extract_document – runs Docling, post-processing, NER, boilerplate tagging
  3. build_structured_json – saves data/extracted/<uuid>.json
  4. audit_extraction – 9-rule QA audit on the saved JSON

Returns (success: bool, json_path: Path | None, error_message: str | None).
"""
import logging
import sys
from pathlib import Path

# Ensure the workspace root is on sys.path so the `extraction` package resolves
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent  # daily/
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from extraction.document_validator import validate_pdf, audit_extraction
from extraction.docling_extractor import extract_document
from extraction.json_builder import build_structured_json
from app.core.config import EXTRACTED_DIR

logger = logging.getLogger(__name__)


def run_extraction(
    file_id: str,
    pdf_path: Path,
) -> tuple[bool, Path | None, str | None]:
    """
    Execute the full extraction pipeline for a single uploaded PDF.

    Args:
        file_id:  UUID of the document record (used for log context and naming).
        pdf_path: Path to the saved PDF file.

    Returns:
        (success, json_path, error_message)
    """
    logger.info(f"[{file_id}] Starting extraction pipeline for: {pdf_path.name}")

    # ── 1. Validate PDF ───────────────────────────────────────────────────────
    val_report = validate_pdf(pdf_path)
    if not val_report.get("is_valid", False):
        errors = val_report.get("errors", ["Unknown validation failure"])
        error_msg = f"PDF Validation failed: {'; '.join(errors)}"
        logger.error(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    logger.info(
        f"[{file_id}] PDF Validated ✓ — "
        f"Pages: {val_report.get('page_count')}, "
        f"Size: {val_report.get('file_size_mb')} MB"
    )

    # ── 2. Run Smart Router Extraction & Post-processing ─────────────────────
    doc_out_dir = EXTRACTED_DIR / file_id
    doc_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_doc, extracted_data = extract_document(pdf_path, doc_out_dir)
    except Exception as exc:
        error_msg = f"Docling extraction failed: {exc}"
        logger.exception(f"[{file_id}] {error_msg}")
        return False, None, error_msg


    if not extracted_data:
        error_msg = "Docling extraction returned empty data"
        logger.error(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    logger.info(f"[{file_id}] Docling extraction completed ✓")

    # ── 3. Build & Save Structured JSON ───────────────────────────────────────
    json_path = EXTRACTED_DIR / f"{file_id}.json"
    try:
        json_path = build_structured_json(
            extracted_data=extracted_data,
            pdf_path=pdf_path,
            validation_report=val_report,
            output_json_path=json_path,
        )
        logger.info(f"[{file_id}] JSON saved → {json_path}")
    except Exception as exc:
        error_msg = f"Failed to build structured JSON: {exc}"
        logger.exception(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    # ── 4. Audit Extraction ───────────────────────────────────────────────────
    audit_results = audit_extraction(json_path)
    failures = [
        rule for rule, passed in audit_results.items()
        if not passed and rule != "audited_at"
    ]
    if failures:
        logger.warning(
            f"[{file_id}] QA Audit reported warning(s) for rules: {failures} "
            f"(JSON saved, proceeding)"
        )
    else:
        logger.info(f"[{file_id}] QA Audit passed cleanly (9/9 rules) ✓")

    return True, json_path, None
