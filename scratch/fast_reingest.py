"""
scratch/fast_reingest.py
Fast in-place re-ingestion of UPSC PDFs.
"""
import os, sys, time, logging, json
from pathlib import Path
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fast_reingest")

def reingest_document(db, doc: Document) -> bool:
    file_id = doc.id
    filename = doc.original_filename
    logger.info(f"[{file_id}] Starting fast re-ingest for: {filename}")
    
    pdf_path = Path(doc.file_path)
    json_path = Path(doc.extracted_json_path) if doc.extracted_json_path else None
    
    if not pdf_path.exists():
        logger.error(f"[{file_id}] PDF file not found at: {pdf_path}")
        return False
    if not json_path or not json_path.exists():
        logger.error(f"[{file_id}] Extracted JSON not found at: {json_path}")
        return False

    try:
        page_widths = {}
        fitz_doc = fitz.open(str(pdf_path))
        for p_idx, page in enumerate(fitz_doc, start=1):
            page_widths[p_idx] = page.rect.width
        fitz_doc.close()
    except Exception as e:
        logger.error(f"[{file_id}] Failed to read PDF page widths: {e}")
        return False

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        text_blocks = data.get("text_blocks", [])
        if not text_blocks:
            logger.warning(f"[{file_id}] No text blocks found in JSON. Skipping re-sort.")
        else:
            data["text_blocks"] = reorder_all_pages(text_blocks, page_widths)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"[{file_id}] Reordered blocks and saved JSON ✓")
    except Exception as e:
        logger.error(f"[{file_id}] Failed to modify extracted JSON: {e}")
        return False

    repository.update_document_status(db, file_id, status="preprocessing")
    pre_success, preprocessed_path, pre_error = run_preprocessing(
        file_id=file_id,
        extracted_json_path=json_path,
    )
    if not pre_success:
        repository.update_document_status(db, file_id, status="failed", error_message=pre_error)
        logger.error(f"[{file_id}] Preprocessing failed: {pre_error}")
        return False
    repository.update_document_status(db, file_id, status="preprocessed", preprocessed_json_path=str(preprocessed_path))

    repository.update_document_status(db, file_id, status="embedding")
    emb_success, embedded_chunks, emb_error = run_embedding(preprocessed_json_path=preprocessed_path)
    if not emb_success or not embedded_chunks:
        repository.update_document_status(db, file_id, status="failed", error_message=emb_error)
        logger.error(f"[{file_id}] Embedding failed: {emb_error}")
        return False

    delete_document_vectors(file_id, doc.classification)

    qdrant_success, qdrant_error = run_qdrant_upsert(
        file_id=file_id,
        classification=doc.classification,
        embedded_chunks=embedded_chunks,
    )
    if not qdrant_success:
        repository.update_document_status(db, file_id, status="failed", error_message=qdrant_error)
        logger.error(f"[{file_id}] Qdrant upsert failed: {qdrant_error}")
        return False

    repository.update_document_status(db, file_id, status="ingested")
    logger.info(f"[{file_id}] Fast re-ingest successfully completed ✓")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fast in-place re-ingestion of UPSC PDFs")
    parser.add_argument("--limit", type=int, default=None, help="Max documents to process")
    parser.add_argument("--file-id", type=str, default=None, help="Process one specific document")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Document)
        if args.file_id:
            query = query.filter(Document.id == args.file_id)
        else:
            query = query.filter(Document.status.in_(["ingested", "preprocessed", "extracted"]))
        docs = query.all()
        if args.limit:
            docs = docs[:args.limit]
        total = len(docs)
        print(f"Found {total} documents to re-ingest.")
        success_count = 0
        failed_count = 0
        t_start = time.time()
        for idx, doc in enumerate(docs, start=1):
            print(f"\n[{idx}/{total}] Processing: {doc.original_filename}")
            success = reingest_document(db, doc)
            if success:
                success_count += 1
            else:
                failed_count += 1
        elapsed = time.time() - t_start
        print(f"\nSucceeded: {success_count} | Failed: {failed_count} | Time: {elapsed/60:.2f} min")
    finally:
        db.close()

if __name__ == "__main__":
    main()
