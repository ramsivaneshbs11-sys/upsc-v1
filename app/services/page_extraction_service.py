"""
page_extraction_service.py
───────────────────────────
Service layer bridging the FastAPI v2 router to the Gemini extraction
orchestrator (gemini_page_extractor.py).

Mirrors the interface of extraction_service.py (Endpoint 1) so the router
code is symmetrical.
"""

import logging
import sys
from pathlib import Path

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from extraction.gemini_page_extractor import extract_document_with_gemini
from extraction.document_validator import validate_pdf, audit_extraction
from extraction.json_builder import build_structured_json
from app.core.config import EXTRACTED_DIR

logger = logging.getLogger(__name__)


def run_gemini_extraction(
    file_id: str,
    pdf_path: Path,
) -> tuple[bool, Path | None, str | None]:
    """
    Execute the full Gemini extraction pipeline for a single uploaded PDF.

    Steps:
        1. Validate PDF
        2. Run extract_document_with_gemini() — iterates all pages via
           text_service + table_service, builds final JSON
        3. Save final JSON to EXTRACTED_DIR/<file_id>.json
        4. Run QA audit

    Args:
        file_id:  UUID of the document record (used for naming and logging).
        pdf_path: Path to the saved PDF file.

    Returns:
        (success, json_path, error_message)
    """
    logger.info(f"[{file_id}] Starting Gemini extraction pipeline: {pdf_path.name}")

    # ── 1. Validate PDF ───────────────────────────────────────────────────────
    val_report = validate_pdf(pdf_path)
    if not val_report.get("is_valid", False):
        errors    = val_report.get("errors", ["Unknown validation failure"])
        error_msg = f"PDF validation failed: {'; '.join(errors)}"
        logger.error(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    logger.info(
        f"[{file_id}] PDF validated ✓ — "
        f"Pages: {val_report.get('page_count')}, "
        f"Size: {val_report.get('file_size_mb')} MB"
    )

    # ── 2. Run Gemini extraction (all pages) ──────────────────────────────────
    doc_out_dir = EXTRACTED_DIR / file_id
    doc_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        _, extracted_data = extract_document_with_gemini(pdf_path, doc_out_dir)
    except Exception as exc:
        error_msg = f"Gemini extraction failed: {exc}"
        logger.exception(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    if not extracted_data:
        error_msg = "Gemini extraction returned empty data"
        logger.error(f"[{file_id}] {error_msg}")
        return False, None, error_msg

    logger.info(f"[{file_id}] Gemini extraction completed ✓")

    # ── 3. Save structured JSON ───────────────────────────────────────────────
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

    # ── 4. QA Audit ───────────────────────────────────────────────────────────
    try:
        audit_results = audit_extraction(json_path)
        failures = [
            rule for rule, passed in audit_results.items()
            if not passed and rule != "audited_at"
        ]
        if failures:
            logger.warning(
                f"[{file_id}] QA audit warnings for rules: {failures} "
                f"(JSON saved, proceeding)"
            )
        else:
            logger.info(f"[{file_id}] QA audit passed ✓")
    except Exception as exc:
        logger.warning(f"[{file_id}] QA audit skipped (non-fatal): {exc}")

    return True, json_path, None
