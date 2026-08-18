"""
resume_failed.py
─────────────────
Recovery script to resume ingestion for failed documents.

This script:
1. Queries the database for all documents where status = 'failed'.
2. Checks if the preprocessed JSON file exists.
3. If it exists, runs embedding generation and Qdrant upsert.
4. Updates status in PostgreSQL to 'ingested' upon success, or logs the new error.
"""

import sys
from pathlib import Path
import logging

# Set up workspace path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("resume_failed")

from app.database.session import SessionLocal
from app.database.models import Document
from app.database import repository
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert

def resume_all_failed():
    db = SessionLocal()
    try:
        failed_docs = db.query(Document).filter(Document.status == 'failed').all()
        if not failed_docs:
            logger.info("No failed documents found in the database. Everything is clean!")
            return

        logger.info(f"Found {len(failed_docs)} failed documents in database. Attempting recovery...")

        recovered_count = 0
        skipped_count = 0
        failed_count = 0

        for doc in failed_docs:
            logger.info(f"\nProcessing failed document: {doc.original_filename} (ID: {doc.id})")
            
            if not doc.preprocessed_json_path:
                logger.warning(f"  -> Skipping: preprocessed_json_path is not defined in DB record.")
                skipped_count += 1
                continue

            prep_path = Path(doc.preprocessed_json_path)
            if not prep_path.exists():
                logger.warning(f"  -> Skipping: Preprocessed JSON file does not exist on disk: {prep_path}")
                skipped_count += 1
                continue

            logger.info(f"  -> Found preprocessed JSON on disk: {prep_path.name}")
            
            # Step 1: Run embedding
            logger.info("  -> Step 1/2: Generating embeddings (BGE)...")
            repository.update_document_status(db, doc.id, status="embedding")
            
            emb_success, embedded_chunks, emb_error = run_embedding(prep_path)
            if not emb_success:
                logger.error(f"  -> [FAIL] Embedding failed: {emb_error}")
                repository.update_document_status(db, doc.id, status="failed", error_message=emb_error)
                failed_count += 1
                continue
            
            logger.info(f"  -> Generated {len(embedded_chunks)} vector embeddings successfully.")

            # Step 2: Run Qdrant upsert
            logger.info(f"  -> Step 2/2: Upserting to Qdrant collection for classification '{doc.classification}'...")
            qdrant_success, qdrant_error = run_qdrant_upsert(
                file_id=doc.id,
                classification=doc.classification,
                embedded_chunks=embedded_chunks
            )
            
            if not qdrant_success:
                logger.error(f"  -> [FAIL] Qdrant upsert failed: {qdrant_error}")
                repository.update_document_status(db, doc.id, status="failed", error_message=qdrant_error)
                failed_count += 1
                continue

            # Ingestion succeeded!
            repository.update_document_status(db, doc.id, status="ingested", error_message=None)
            logger.info(f"  -> [SUCCESS] Document '{doc.original_filename}' successfully ingested!")
            recovered_count += 1

        logger.info("\n" + "="*50)
        logger.info("RECOVERY COMPLETED")
        logger.info(f"  Successfully recovered: {recovered_count}")
        logger.info(f"  Skipped (no files)    : {skipped_count}")
        logger.info(f"  Failed again          : {failed_count}")
        logger.info("="*50)

    except Exception as e:
        logger.exception(f"Recovery failed due to exception: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    resume_all_failed()
