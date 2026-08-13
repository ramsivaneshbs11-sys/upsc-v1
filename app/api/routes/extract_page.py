"""
app/api/routes/extract_page.py
────────────────────────────────
Endpoint 2: POST /api/v2/documents

Full-document extraction using Gemini 2.5 Flash (text + table extraction
per page, merged into a single final JSON).

Pipeline (identical to v1 except for the extraction engine):
  1.  Validate classification & file extension
  2.  Generate UUID (file_id)
  3.  Save PDF to uploads/<classification>/<file_id>.pdf
  4.  Register document in PostgreSQL        →  status = registered
  5.  Update status                          →  status = extracting
  6.  Run Gemini 2.5 Flash extraction (all pages, text + tables)
  7a. Success → Update status               →  status = extracted
  7b. Failure → Update status               →  status = failed
  8.  Update status                          →  status = preprocessing
  8a. Run preprocessing + chunking
  8b. Success → Update status               →  status = preprocessed
  8c. Failure → Update status               →  status = failed
  9.  Update status                          →  status = embedding
  9a. Run BGE embedding (BAAI/bge-base-en-v1.5)
  9b. Failure → Update status               →  status = failed
  10. Run Qdrant upsert
  10a. Success → Update status              →  status = ingested
  10b. Failure → Update status              →  status = failed
  11. Return JSON response
"""

import uuid
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import ALLOWED_CLASSIFICATIONS
from app.database.session import get_db
from app.database import repository
from app.services.storage_service import save_uploaded_pdf
from app.services.page_extraction_service import run_gemini_extraction
from app.services.preprocessing_service import run_preprocessing
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["documents-v2"])


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def register_and_extract_gemini(
    file: UploadFile = File(..., description="PDF file to ingest"),
    classification: str = Form(
        ..., description="Document classification: History or Anthropology"
    ),
    db: Session = Depends(get_db),
):
    """
    Register a PDF and run the **Gemini 2.5 Flash** full-document extraction pipeline.

    Per-page flow:
    - **text_service** → extract all text (headings, paragraphs, list items) verbatim
    - **table_service** → extract all tables
    - Both merged into a single page JSON; pages merged into final document JSON

    **Pipeline:** Validate → Save → Register (PostgreSQL) → Extract (Gemini 2.5 Flash)
    → Preprocess + Chunk → Embed (BGE) → Upsert (Qdrant)

    Only the extraction engine differs from v1 (Docling + Tesseract OCR).
    All downstream steps are identical to /api/v1/documents.

    - **file**: PDF file (multipart/form-data)
    - **classification**: One of `History` or `Anthropology`
    """

    # ── Step 1: Validate inputs ───────────────────────────────────────────────
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid classification '{classification}'. "
                f"Allowed: {ALLOWED_CLASSIFICATIONS}"
            ),
        )

    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # ── Step 2: Generate UUID ─────────────────────────────────────────────────
    file_id = str(uuid.uuid4())
    logger.info(
        f"[v2] New document request → id={file_id}, file={filename}, class={classification}"
    )

    # ── Step 3: Save PDF to disk ──────────────────────────────────────────────
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        saved_path = save_uploaded_pdf(file_id, classification, tmp_path)
        logger.info(f"[v2][{file_id}] PDF saved → {saved_path}")
    except Exception as exc:
        logger.exception(f"[v2][{file_id}] Failed to save uploaded file: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save PDF: {exc}")

    # ── Step 4: Register in PostgreSQL ────────────────────────────────────────
    doc = repository.create_document(
        db=db,
        file_id=file_id,
        original_filename=filename,
        classification=classification,
        file_path=str(saved_path),
    )
    logger.info(f"[v2][{file_id}] Registered in PostgreSQL — status=registered")

    # ── Step 5: Update status → extracting ───────────────────────────────────
    repository.update_document_status(db, file_id, status="extracting")

    # ── Step 6: Run Gemini extraction ─────────────────────────────────────────
    success, json_path, error_msg = run_gemini_extraction(
        file_id=file_id,
        pdf_path=saved_path,
    )

    # ── Steps 7a / 7b ─────────────────────────────────────────────────────────
    if not success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=error_msg
        )
        logger.error(f"[v2][{file_id}] Gemini extraction failed → {error_msg}")
        return _build_response(final_doc)

    final_doc = repository.update_document_status(
        db, file_id, status="extracted", extracted_json_path=str(json_path)
    )
    logger.info(f"[v2][{file_id}] Gemini extraction complete ✓ → status=extracted")

    # ── Step 8: Preprocessing + Chunking ─────────────────────────────────────
    repository.update_document_status(db, file_id, status="preprocessing")

    pre_success, preprocessed_path, pre_error = run_preprocessing(
        file_id=file_id,
        extracted_json_path=json_path,
    )

    if not pre_success:
        final_doc = repository.update_document_status(
            db, file_id, status="failed", error_message=pre_error
        )
        logger.error(f"[v2][{file_id}] Preprocessing failed → {pre_error}")
        return _build_response(final_doc)

    final_doc = repository.update_document_status(
        db, file_id, status="preprocessed",
        preprocessed_json_path=str(preprocessed_path),
    )
    logger.info(f"[v2][{file_id}] Preprocessing complete ✓ → status=preprocessed")

    # ── Step 9: Embedding ─────────────────────────────────────────────────────
    repository.update_document_status(db, file_id, status="embedding")
    logger.info(f"[v2][{file_id}] Status updated → embedding")

    emb_success, embedded_chunks, emb_error = run_embedding(
        preprocessed_json_path=preprocessed_path,
    )

    if not emb_success:
        final_doc = repository.update_document_status(
            db,
            file_id,
            status="failed",
            error_message=emb_error,
        )
        logger.error(f"[v2][{file_id}] Embedding failed → status=failed | {emb_error}")
        return _build_response(final_doc)

    logger.info(f"[v2][{file_id}] Embedding complete ✓ — {len(embedded_chunks)} vectors")

    # ── Step 10: Qdrant Upsert ────────────────────────────────────────────────
    qdrant_success, qdrant_error = run_qdrant_upsert(
        file_id=file_id,
        classification=classification,
        embedded_chunks=embedded_chunks,
    )

    if not qdrant_success:
        final_doc = repository.update_document_status(
            db,
            file_id,
            status="failed",
            error_message=qdrant_error,
        )
        logger.error(f"[v2][{file_id}] Qdrant upsert failed → status=failed | {qdrant_error}")
        return _build_response(final_doc)

    # ── Step 11: Mark as fully ingested ──────────────────────────────────────
    final_doc = repository.update_document_status(db, file_id, status="ingested")
    logger.info(f"[v2][{file_id}] Full pipeline complete ✓ → status=ingested")

    return _build_response(final_doc)


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_response(doc) -> dict:
    """Serialize a Document ORM object to a response dict."""
    return {
        "document_id":             doc.id,
        "original_filename":       doc.original_filename,
        "classification":          doc.classification,
        "extraction_engine":       "gemini-2.5-flash",
        "file_path":               doc.file_path,
        "extracted_json_path":     doc.extracted_json_path,
        "preprocessed_json_path":  doc.preprocessed_json_path,
        "status":                  doc.status,
        "error_message":           doc.error_message,
        "created_at":              doc.created_at.isoformat(),
        "updated_at":              doc.updated_at.isoformat(),
    }

