"""
ide_gemini_ingest.py
─────────────────────────────────────────────────────────────────────────────
Standalone ingestion script for PDFs extracted using the Antigravity IDE
Built-in Gemini Flash Vision model.

Use this when you have manually extracted a PDF through the IDE (for complex
scanned/handwritten PDFs) and the agent has saved the extraction output as a
structured JSON file. This script will then run all the pipeline steps that
normally happen before and after extraction in the full endpoint pipeline:

  BEFORE (simulated — no actual file upload):
    1.  Generate UUID for the document
    2.  Copy/save PDF to uploads/<classification>/<uuid>.pdf (local)
    3.  Register document in PostgreSQL  →  status = registered

  AFTER (using your pre-existing IDE Gemini extraction JSON):
    4.  Mark status                      →  status = extracting
    5.  Store extracted_json_path        →  status = extracted
    6.  Preprocessing & Chunking         →  status = preprocessing → preprocessed
    7.  BGE Embedding                    →  status = embedding
    8.  Qdrant Upsert                    →  status = ingested

Usage (how to run — see bottom of this file for prompt):
    python ide_gemini_ingest.py <path_to_extracted_json> --pdf <path_to_pdf> --classification Anthropology

Example:
    python ide_gemini_ingest.py scratch/test_gemini_out/145793840413ET_gemini.json ^
        --pdf 145793840413ET.pdf ^
        --classification Anthropology

NOTE:
    Make sure PostgreSQL and Qdrant are running before executing this script.
    docker compose up -d

Requirements:
    pip install psycopg2-binary sqlalchemy sentence-transformers qdrant-client
"""

import sys
import os
import uuid
import json
import shutil
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ide_gemini_ingest")

DIVIDER = "=" * 65


# ── Step helpers ──────────────────────────────────────────────────────────────

def step_banner(n: int, title: str):
    print(f"\n  -- Step {n}: {title}")


def ok(msg: str):
    print(f"  [OK]   {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(
    extracted_json: Path,
    pdf_path: Path,
    classification: str,
):
    """
    Executes all pipeline steps for a PDF that was already extracted via
    the Antigravity IDE Gemini Flash Vision.
    """

    print(f"\n{DIVIDER}")
    print(f"  IDE GEMINI INGEST PIPELINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  PDF            : {pdf_path.name}")
    print(f"  Extracted JSON : {extracted_json.name}")
    print(f"  Classification : {classification}")
    print(DIVIDER)

    # ─── Step 1: Generate UUID ────────────────────────────────────────────────
    step_banner(1, "Generate UUID")
    file_id = str(uuid.uuid4())
    ok(f"file_id = {file_id}")

    # ─── Step 2: Save PDF to uploads/<classification>/<uuid>.pdf ─────────────
    step_banner(2, "Save PDF locally")
    from app.services.storage_service import save_uploaded_pdf
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copy2(pdf_path, tmp.name)
            tmp_path = Path(tmp.name)
        saved_path = save_uploaded_pdf(file_id, classification, tmp_path)
        ok(f"Saved -> {saved_path}")
    except Exception as e:
        fail(f"Failed to save PDF: {e}")
        sys.exit(1)

    # ─── Step 3: Register in PostgreSQL ──────────────────────────────────────
    step_banner(3, "Register in PostgreSQL")
    from app.database.session import SessionLocal
    from app.database import repository

    db = SessionLocal()
    try:
        doc = repository.create_document(
            db=db,
            file_id=file_id,
            original_filename=pdf_path.name,
            classification=classification,
            file_path=str(saved_path),
        )
        ok(f"Registered -> document_id={doc.id}, status=registered")
    except Exception as e:
        db.close()
        fail(f"PostgreSQL registration failed: {e}")
        sys.exit(1)

    # ─── Step 4 & 5: Mark as extracted (IDE JSON used directly) ──────────────
    step_banner(4, "Register IDE Gemini JSON as extraction output")
    repository.update_document_status(db, file_id, status="extracting")

    # Copy the IDE gemini JSON to the standard output location (data/extracted/<file_id>.json)
    from app.core.config import EXTRACTED_DIR
    json_dest = EXTRACTED_DIR / f"{file_id}.json"

    try:
        shutil.copy2(extracted_json, json_dest)
        ok(f"IDE Gemini JSON copied -> {json_dest}")
    except Exception as e:
        repository.update_document_status(db, file_id, status="failed", error_message=str(e))
        db.close()
        fail(f"Failed to copy extracted JSON: {e}")
        sys.exit(1)

    repository.update_document_status(
        db, file_id, status="extracted",
        extracted_json_path=str(json_dest)
    )
    ok(f"Status -> extracted")

    # ─── Step 6: Preprocessing & Chunking ────────────────────────────────────
    step_banner(5, "Preprocessing & Chunking")
    repository.update_document_status(db, file_id, status="preprocessing")

    from app.services.preprocessing_service import run_preprocessing
    pre_success, preprocessed_path, pre_error = run_preprocessing(
        file_id=file_id,
        extracted_json_path=json_dest,
    )

    if not pre_success:
        repository.update_document_status(db, file_id, status="failed", error_message=pre_error)
        db.close()
        fail(f"Preprocessing failed: {pre_error}")
        sys.exit(1)

    repository.update_document_status(
        db, file_id, status="preprocessed",
        preprocessed_json_path=str(preprocessed_path)
    )
    ok(f"Preprocessed -> {preprocessed_path}")

    # ─── Step 7: BGE Embedding ────────────────────────────────────────────────
    step_banner(6, "BGE Embedding (bge-base-en-v1.5)")
    repository.update_document_status(db, file_id, status="embedding")

    from app.services.embedding_service import run_embedding
    emb_success, embedded_chunks, emb_error = run_embedding(
        preprocessed_json_path=preprocessed_path,
    )

    if not emb_success:
        repository.update_document_status(db, file_id, status="failed", error_message=emb_error)
        db.close()
        fail(f"Embedding failed: {emb_error}")
        sys.exit(1)

    ok(f"Embedded {len(embedded_chunks)} chunks")

    # ─── Step 8: Qdrant Upsert ────────────────────────────────────────────────
    step_banner(7, "Qdrant Upsert")
    from app.services.qdrant_service import run_qdrant_upsert
    qdrant_success, qdrant_error = run_qdrant_upsert(
        file_id=file_id,
        classification=classification,
        embedded_chunks=embedded_chunks,
    )

    if not qdrant_success:
        repository.update_document_status(db, file_id, status="failed", error_message=qdrant_error)
        db.close()
        fail(f"Qdrant upsert failed: {qdrant_error}")
        sys.exit(1)

    # ─── Step 9: Final status ─────────────────────────────────────────────────
    final_doc = repository.update_document_status(db, file_id, status="ingested")
    db.close()

    print(f"\n{DIVIDER}")
    print(f"  PIPELINE COMPLETE SUCCESS")
    print(f"  document_id     : {final_doc.id}")
    print(f"  file_id (UUID)  : {file_id}")
    print(f"  PDF saved at    : {saved_path}")
    print(f"  Extracted JSON  : {json_dest}")
    print(f"  Preprocessed    : {preprocessed_path}")
    print(f"  Vectors upserted: {len(embedded_chunks)}")
    print(f"  Final status    : {final_doc.status}")
    print(DIVIDER)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "IDE Gemini Flash Vision Ingest Script\n"
            "──────────────────────────────────────\n"
            "Runs the full pre + post extraction pipeline for a PDF that\n"
            "was already extracted using the Antigravity IDE built-in model.\n\n"
            "Usage:\n"
            "  python ide_gemini_ingest.py <extracted_json> --pdf <pdf_path> --classification <class>\n\n"
            "Example:\n"
            "  python ide_gemini_ingest.py scratch/test_gemini_out/145793840413ET_gemini.json \\\n"
            "      --pdf 145793840413ET.pdf \\\n"
            "      --classification Anthropology"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "extracted_json",
        type=str,
        help="Path to the extracted JSON file produced by IDE Gemini Flash Vision.",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="Path to the original PDF file.",
    )
    parser.add_argument(
        "--classification",
        type=str,
        required=True,
        choices=["History", "Anthropology"],
        help="Document classification: 'History' or 'Anthropology'",
    )

    args = parser.parse_args()

    extracted_json = Path(args.extracted_json)
    pdf_path = Path(args.pdf)

    if not extracted_json.exists():
        logger.error(f"Extracted JSON not found: {extracted_json}")
        sys.exit(1)

    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)

    run(
        extracted_json=extracted_json,
        pdf_path=pdf_path,
        classification=args.classification,
    )


if __name__ == "__main__":
    main()
