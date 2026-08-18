"""
app/api/routes/documents.py
────────────────────────────
v1 ingestion endpoints (Docling extractor).

Endpoints:
  POST /api/v1/documents               — upload one or more PDF files
  POST /api/v1/documents/folder        — ingest all PDFs in a server-side folder path
  POST /api/v1/documents/retry-failed  — resume all failed documents from embedding step

Pipeline per file (fully sequential):
  Validate → Save → Register (PostgreSQL) → Extract (Docling)
  → Preprocess + Chunk → Embed (BGE) → Upsert (Qdrant) → Return JSON
"""
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import ALLOWED_CLASSIFICATIONS
from app.database.session import get_db
from app.database.models import Document
from app.database import repository
from app.services.extraction_service import run_extraction
from app.services.ingest_pipeline import run_single_ingest
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["documents"])


# ── Request body for folder ingestion ─────────────────────────────────────────

class FolderIngestRequest(BaseModel):
    folder_path: str
    classification: str


# ── Multi-file upload endpoint ────────────────────────────────────────────────

@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def ingest_files(
    files: List[UploadFile] = File(..., description="One or more PDF files to ingest"),
    classification: str = Form(
        ..., description="Document classification: History or Anthropology"
    ),
    db: Session = Depends(get_db),
):
    """
    Upload **one or more** PDF files and run the full ingestion pipeline for each.

    - **files**: Select one or multiple `.pdf` files (multipart/form-data)
    - **classification**: `History` or `Anthropology`

    Returns a list — one result object per uploaded file.

    Pipeline per file: Validate → Save → Register → Extract (Docling)
    → Preprocess → Embed → Qdrant upsert
    """
    # ── Validate classification ───────────────────────────────────────────────
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification '{classification}'. Allowed: {ALLOWED_CLASSIFICATIONS}",
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # ── Validate that all uploads are PDFs before starting any pipeline ───────
    for f in files:
        filename = f.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"'{filename}' is not a PDF. Only .pdf files are accepted.",
            )

    # ── Process each file sequentially ───────────────────────────────────────
    results = []
    for upload in files:
        filename = upload.filename or "unknown.pdf"
        logger.info(f"Processing upload: {filename}")
        pdf_bytes = await upload.read()
        result = run_single_ingest(
            filename=filename,
            classification=classification,
            pdf_bytes=pdf_bytes,
            db=db,
            extractor_fn=run_extraction,
        )
        results.append(result)

    return results


# ── Folder ingestion endpoint ─────────────────────────────────────────────────

@router.post("/documents/folder", status_code=status.HTTP_201_CREATED)
def ingest_folder(
    body: FolderIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Ingest **all PDF files** found inside a server-side folder path.

    Provide the absolute path to a folder on the server that contains PDF files.
    The endpoint will recursively discover all `*.pdf` files and run the full
    ingestion pipeline for each one.

    ```json
    {
      "folder_path": "C:/data/pdfs/history",
      "classification": "History"
    }
    ```

    Returns a list — one result object per discovered PDF.

    Pipeline per file: Validate → Save → Register → Extract (Docling)
    → Preprocess → Embed → Qdrant upsert
    """
    # ── Validate classification ───────────────────────────────────────────────
    if body.classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid classification '{body.classification}'. "
                f"Allowed: {ALLOWED_CLASSIFICATIONS}"
            ),
        )

    # ── Validate folder path ──────────────────────────────────────────────────
    folder = Path(body.folder_path)
    if not folder.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Folder not found: '{body.folder_path}'",
        )
    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: '{body.folder_path}'",
        )

    # ── Discover PDFs ─────────────────────────────────────────────────────────
    pdf_files = sorted(folder.rglob("*.pdf"))
    if not pdf_files:
        raise HTTPException(
            status_code=400,
            detail=f"No PDF files found in folder: '{body.folder_path}'",
        )

    logger.info(
        f"Folder ingest (v1) — found {len(pdf_files)} PDFs in '{folder}' "
        f"| classification={body.classification}"
    )

    # ── Process each PDF sequentially ────────────────────────────────────────
    results = []
    for pdf_path in pdf_files:
        logger.info(f"Processing PDF from folder: {pdf_path.name}")
        try:
            pdf_bytes = pdf_path.read_bytes()
        except Exception as exc:
            logger.error(f"Cannot read '{pdf_path}': {exc}")
            results.append({
                "document_id": None,
                "original_filename": pdf_path.name,
                "classification": body.classification,
                "status": "failed",
                "error_message": f"Cannot read file: {exc}",
            })
            continue

        result = run_single_ingest(
            filename=pdf_path.name,
            classification=body.classification,
            pdf_bytes=pdf_bytes,
            db=db,
            extractor_fn=run_extraction,
        )
        results.append(result)

    return {
        "folder": str(folder),
        "classification": body.classification,
        "total_pdfs": len(pdf_files),
        "results": results,
    }


# ── Retry-failed endpoint ─────────────────────────────────────────────────────

@router.post("/documents/retry-failed", status_code=status.HTTP_200_OK)
def retry_failed_documents(
    db: Session = Depends(get_db),
):
    """
    Resume ingestion for all documents currently marked as **failed** in PostgreSQL.

    For each failed document this endpoint:
    - Checks the `preprocessed_json_path` stored in the DB record exists on disk.
    - If it exists, **skips** extraction and preprocessing entirely.
    - Runs **BGE embedding** directly on the preprocessed JSON.
    - Upserts the vectors to the correct **Qdrant** collection.
    - Updates status to `ingested` on success, or records the new error on failure.

    Documents whose preprocessed JSON is missing on disk are skipped with a
    `needs_reprocessing` status — they require a full re-ingest.

    Returns a summary report with per-document results.
    """
    failed_docs = db.query(Document).filter(Document.status == "failed").all()

    if not failed_docs:
        return {
            "message": "No failed documents found. Everything is clean!",
            "recovered": 0,
            "skipped": 0,
            "still_failed": 0,
            "results": [],
        }

    logger.info(f"retry-failed: Found {len(failed_docs)} failed document(s). Starting recovery...")

    results = []
    recovered = 0
    skipped = 0
    still_failed = 0

    for doc in failed_docs:
        entry = {
            "document_id": doc.id,
            "original_filename": doc.original_filename,
            "classification": doc.classification,
            "previous_error": doc.error_message,
        }

        # ── Guard: preprocessed JSON must exist on disk ────────────────────────
        if not doc.preprocessed_json_path:
            entry["status"] = "skipped"
            entry["reason"] = "preprocessed_json_path not set in DB — full re-ingest required."
            logger.warning(f"[{doc.id}] retry-failed: skipped — no preprocessed_json_path.")
            results.append(entry)
            skipped += 1
            continue

        prep_path = Path(doc.preprocessed_json_path)
        if not prep_path.exists():
            entry["status"] = "skipped"
            entry["reason"] = f"Preprocessed JSON missing on disk: {prep_path.name} — full re-ingest required."
            logger.warning(f"[{doc.id}] retry-failed: skipped — file not found: {prep_path}")
            results.append(entry)
            skipped += 1
            continue

        # ── Step 1: Embedding ─────────────────────────────────────────────────
        repository.update_document_status(db, doc.id, status="embedding")
        emb_success, embedded_chunks, emb_error = run_embedding(prep_path)

        if not emb_success:
            repository.update_document_status(db, doc.id, status="failed", error_message=emb_error)
            entry["status"] = "failed"
            entry["error"] = emb_error
            logger.error(f"[{doc.id}] retry-failed: embedding failed: {emb_error}")
            results.append(entry)
            still_failed += 1
            continue

        # ── Step 2: Qdrant upsert ─────────────────────────────────────────────
        qdrant_success, qdrant_error = run_qdrant_upsert(
            file_id=doc.id,
            classification=doc.classification,
            embedded_chunks=embedded_chunks,
        )

        if not qdrant_success:
            repository.update_document_status(db, doc.id, status="failed", error_message=qdrant_error)
            entry["status"] = "failed"
            entry["error"] = qdrant_error
            logger.error(f"[{doc.id}] retry-failed: qdrant upsert failed: {qdrant_error}")
            results.append(entry)
            still_failed += 1
            continue

        # ── Success ───────────────────────────────────────────────────────────
        repository.update_document_status(db, doc.id, status="ingested", error_message=None)
        entry["status"] = "ingested"
        entry["vectors_upserted"] = len(embedded_chunks)
        logger.info(f"[{doc.id}] retry-failed: '{doc.original_filename}' recovered successfully.")
        results.append(entry)
        recovered += 1

    logger.info(
        f"retry-failed complete — recovered={recovered}, "
        f"skipped={skipped}, still_failed={still_failed}"
    )

    return {
        "message": "Retry complete.",
        "total_failed_found": len(failed_docs),
        "recovered": recovered,
        "skipped": skipped,
        "still_failed": still_failed,
        "results": results,
    }
