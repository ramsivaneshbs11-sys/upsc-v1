"""
app/services/ingest_pipeline.py
────────────────────────────────
Shared, reusable ingest pipeline that is called by every ingestion route
(single file, multi-file, folder) for both extractor variants:
  - Docling  (v1) → pass extractor="docling"
  - Gemini   (v2) → pass extractor="gemini"

Returned dict mirrors _build_response() so every route can return it directly.
"""

import uuid
import logging
import tempfile
from pathlib import Path
from typing import Literal, Callable

from sqlalchemy.orm import Session

from app.database import repository
from app.services.storage_service import save_uploaded_pdf
from app.services.preprocessing_service import run_preprocessing
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert

logger = logging.getLogger(__name__)

# Extractor type alias
ExtractorFn = Callable[[str, Path], tuple[bool, Path | None, str | None]]


def run_single_ingest(
    *,
    filename: str,
    classification: str,
    pdf_bytes: bytes,
    db: Session,
    extractor_fn: ExtractorFn,
) -> dict:
    """
    Execute the full ingestion pipeline for one PDF.

    Args:
        filename:       Original PDF filename (used for DB record).
        classification: "History" or "Anthropology".
        pdf_bytes:      Raw bytes of the PDF (from upload or disk read).
        db:             SQLAlchemy session.
        extractor_fn:   Callable matching signature run_extraction /
                        run_gemini_extraction  →  (bool, Path|None, str|None).

    Returns:
        A dict compatible with the existing _build_response() format.
    """
    file_id = str(uuid.uuid4())
    logger.info(
        f"[{file_id}] Ingestion start → file={filename}, class={classification}"
    )

    # ── Step 1: Save PDF to disk ──────────────────────────────────────────────
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)

        saved_path = save_uploaded_pdf(file_id, classification, tmp_path)
        logger.info(f"[{file_id}] PDF saved → {saved_path}")
    except Exception as exc:
        logger.exception(f"[{file_id}] Failed to save file: {exc}")
        return _error_response(file_id, filename, classification, str(exc))

    # ── Step 2: Register in PostgreSQL (status = registered) ─────────────────
    doc = repository.create_document(
        db=db,
        file_id=file_id,
        original_filename=filename,
        classification=classification,
        file_path=str(saved_path),
    )
    logger.info(f"[{file_id}] Registered in PostgreSQL — status=registered")

    # ── Step 3: Extract ───────────────────────────────────────────────────────
    repository.update_document_status(db, file_id, status="extracting")
    success, json_path, error_msg = extractor_fn(file_id=file_id, pdf_path=saved_path)

    if not success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=error_msg
        )
        logger.error(f"[{file_id}] Extraction failed: {error_msg}")
        return _build_response(final_doc)

    final_doc = repository.update_document_status(
        db, file_id, status="extracted", extracted_json_path=str(json_path)
    )
    logger.info(f"[{file_id}] Extraction complete ✓")

    # ── Step 4: Preprocessing + Chunking ─────────────────────────────────────
    repository.update_document_status(db, file_id, status="preprocessing")
    pre_success, preprocessed_path, pre_error = run_preprocessing(
        file_id=file_id,
        extracted_json_path=json_path,
    )

    if not pre_success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=pre_error
        )
        logger.error(f"[{file_id}] Preprocessing failed: {pre_error}")
        return _build_response(final_doc)

    final_doc = repository.update_document_status(
        db, file_id, status="preprocessed",
        preprocessed_json_path=str(preprocessed_path),
    )
    logger.info(f"[{file_id}] Preprocessing complete ✓")

    # ── Step 5: Embedding ─────────────────────────────────────────────────────
    repository.update_document_status(db, file_id, status="embedding")
    emb_success, embedded_chunks, emb_error = run_embedding(
        preprocessed_json_path=preprocessed_path,
    )

    if not emb_success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=emb_error
        )
        logger.error(f"[{file_id}] Embedding failed: {emb_error}")
        return _build_response(final_doc)

    logger.info(f"[{file_id}] Embedding complete ✓ — {len(embedded_chunks)} vectors")

    # ── Step 6: Qdrant Upsert ─────────────────────────────────────────────────
    qdrant_success, qdrant_error = run_qdrant_upsert(
        file_id=file_id,
        classification=classification,
        embedded_chunks=embedded_chunks,
    )

    if not qdrant_success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=qdrant_error
        )
        logger.error(f"[{file_id}] Qdrant upsert failed: {qdrant_error}")
        return _build_response(final_doc)

    # ── Step 7: Done ──────────────────────────────────────────────────────────
    final_doc = repository.update_document_status(db, file_id, status="ingested")
    logger.info(f"[{file_id}] Full pipeline complete ✓ → status=ingested")
    return _build_response(final_doc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_response(doc) -> dict:
    """Serialize a Document ORM object to a response dict."""
    return {
        "document_id": doc.id,
        "original_filename": doc.original_filename,
        "classification": doc.classification,
        "file_path": doc.file_path,
        "extracted_json_path": doc.extracted_json_path,
        "preprocessed_json_path": doc.preprocessed_json_path,
        "status": doc.status,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


def _error_response(file_id: str, filename: str, classification: str, error: str) -> dict:
    """Return an error dict without a DB record (used when save fails before registration)."""
    return {
        "document_id": file_id,
        "original_filename": filename,
        "classification": classification,
        "file_path": None,
        "extracted_json_path": None,
        "preprocessed_json_path": None,
        "status": "failed",
        "error_message": f"Pre-registration failure: {error}",
        "created_at": None,
        "updated_at": None,
    }
