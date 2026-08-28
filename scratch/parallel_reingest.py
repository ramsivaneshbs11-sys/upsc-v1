"""
scratch/parallel_reingest.py
─────────────────────────────
Parallel re-ingestion of UPSC PDFs using a Thread Pool.
This updates all existing documents to the correct top-to-bottom reading order.
Usage:
    python scratch/parallel_reingest.py --workers 4
"""
import os
import sys
import time
import logging
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz  # PyMuPDF

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from app.database.session import SessionLocal
from app.database.models import Document
from app.database import repository
from extraction.reorder_blocks import reorder_all_pages
from app.services.preprocessing_service import run_preprocessing
from app.services.embedding_service import run_embedding
from app.services.qdrant_service import run_qdrant_upsert, delete_document_vectors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s — %(message)s"
)
logger = logging.getLogger("parallel_reingest")


def reingest_document(doc_id: str) -> bool:
    """Re-ingest a single document by ID (run within thread pool)."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error(f"[{doc_id}] Document not found in DB.")
            return False

        filename = doc.original_filename
        logger.info(f"[{doc_id}] Starting re-ingest for: {filename}")

        pdf_path = Path(doc.file_path)
        json_path = Path(doc.extracted_json_path) if doc.extracted_json_path else None

        if not pdf_path.exists():
            logger.error(f"[{doc_id}] PDF file not found at: {pdf_path}")
            return False
        if not json_path or not json_path.exists():
            logger.error(f"[{doc_id}] Extracted JSON not found at: {json_path}")
            return False

        # 1. Read PDF page widths
        page_widths = {}
        try:
            fitz_doc = fitz.open(str(pdf_path))
            for p_idx, page in enumerate(fitz_doc, start=1):
                page_widths[p_idx] = page.rect.width
            fitz_doc.close()
        except Exception as e:
            logger.error(f"[{doc_id}] Failed to read PDF page widths: {e}")
            return False

        # 2. Re-sort text blocks in the extracted JSON using corrected reading order
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text_blocks = data.get("text_blocks", [])
            if not text_blocks:
                logger.warning(f"[{doc_id}] No text blocks found in JSON. Skipping re-sort.")
            else:
                data["text_blocks"] = reorder_all_pages(text_blocks, page_widths)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"[{doc_id}] Reordered blocks and saved JSON ✓")
        except Exception as e:
            logger.error(f"[{doc_id}] Failed to modify extracted JSON: {e}")
            return False

        # 3. Preprocess & chunk
        repository.update_document_status(db, doc_id, status="preprocessing")
        pre_success, preprocessed_path, pre_error = run_preprocessing(
            file_id=doc_id,
            extracted_json_path=json_path,
        )
        if not pre_success:
            repository.update_document_status(db, doc_id, status="failed", error_message=pre_error)
            logger.error(f"[{doc_id}] Preprocessing failed: {pre_error}")
            return False
        repository.update_document_status(db, doc_id, status="preprocessed", preprocessed_json_path=str(preprocessed_path))

        # 4. Embed chunks
        repository.update_document_status(db, doc_id, status="embedding")
        emb_success, embedded_chunks, emb_error = run_embedding(preprocessed_json_path=preprocessed_path)
        if not emb_success or not embedded_chunks:
            repository.update_document_status(db, doc_id, status="failed", error_message=emb_error)
            logger.error(f"[{doc_id}] Embedding failed: {emb_error}")
            return False

        # 5. Delete old Qdrant vectors and upsert new correct ones
        delete_document_vectors(doc_id, doc.classification)
        qdrant_success, qdrant_error = run_qdrant_upsert(
            file_id=doc_id,
            classification=doc.classification,
            embedded_chunks=embedded_chunks,
        )
        if not qdrant_success:
            repository.update_document_status(db, doc_id, status="failed", error_message=qdrant_error)
            logger.error(f"[{doc_id}] Qdrant upsert failed: {qdrant_error}")
            return False

        repository.update_document_status(db, doc_id, status="ingested")
        logger.info(f"[{doc_id}] Re-ingest successfully completed ✓")
        return True

    except Exception as e:
        logger.exception(f"[{doc_id}] Unexpected error: {e}")
        return False
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel re-ingestion of UPSC PDFs")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker threads")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    args = parser.parse_args()

    # Pre-warm embedding model once in main thread to avoid thread race conditions
    logger.info("Pre-warming BGE embedding model...")
    from app.services.embedding_service import _get_model as preload_embedding
    preload_embedding()

    db = SessionLocal()
    try:
        # Fetch ingested documents
        query = db.query(Document).filter(Document.status == "ingested")
        docs = query.all()
        if args.limit:
            docs = docs[:args.limit]

        total = len(docs)
        logger.info(f"Found {total} ingested documents to re-process using {args.workers} workers.")

        if total == 0:
            return

        doc_ids = [d.id for d in docs]
        success_count = 0
        failed_count = 0
        t_start = time.time()

        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="ReingestWorker") as executor:
            future_to_doc = {executor.submit(reingest_document, doc_id): doc_id for doc_id in doc_ids}
            for future in as_completed(future_to_doc):
                doc_id = future_to_doc[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as exc:
                    logger.error(f"[{doc_id}] Thread generated an exception: {exc}")
                    failed_count += 1

        elapsed = time.time() - t_start
        logger.info(f"Completed! Succeeded: {success_count} | Failed: {failed_count} | Time: {elapsed/60:.2f} min")

    finally:
        db.close()


if __name__ == "__main__":
    main()
