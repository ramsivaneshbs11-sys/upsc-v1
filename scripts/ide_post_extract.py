import sys
import os
import json
import shutil
import logging
import argparse
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
logger = logging.getLogger("ide_post_extract")

DIVIDER = "=" * 65

def step_banner(n: int, title: str):
    print(f"\n  -- Step {n}: {title}")

def ok(msg: str):
    print(f"  [OK]   {msg}")

def fail(msg: str):
    print(f"  [FAIL] {msg}")

def run_post_extraction(file_id: str, force: bool = False):
    """
    Executes the post-extraction steps:
      1. Merge batch JSON files
      2. Save to data/extracted/<uuid>.json
      3. Run pre-processing & chunking
      4. Run BGE embedding
      5. Upsert to Qdrant
      6. Update PostgreSQL status to ingested
    """
    from app.database.session import SessionLocal
    from app.database import repository
    from app.core.config import EXTRACTED_DIR

    print(f"\n{DIVIDER}")
    print(f"  IDE POST-EXTRACTION INGEST — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Document UUID  : {file_id}")
    print(DIVIDER)

    temp_dir = ROOT_DIR / "data" / "temp_extraction" / file_id
    manifest_path = temp_dir / "manifest.json"

    if not temp_dir.exists():
        print(f"  [FAIL] Temporary extraction folder not found: {temp_dir}")
        sys.exit(1)

    if not manifest_path.exists():
        print(f"  [FAIL] manifest.json not found in {temp_dir}")
        sys.exit(1)

    # Load manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    classification = manifest.get("classification")
    total_pages = manifest.get("total_pages", 0)
    original_filename = manifest.get("original_filename", "unknown")

    # ── Step 1: Find and merge batch JSON files ───────────────────────────────
    step_banner(1, "Merge batch JSONs")
    
    batch_files = list(temp_dir.glob("batch_*.json"))
    if not batch_files:
        print("  [FAIL] No batch_*.json files found in temporary directory.")
        sys.exit(1)

    print(f"  Found {len(batch_files)} batch files.")

    merged_pages = []
    seen_pages = set()

    for bf in batch_files:
        try:
            with open(bf, "r", encoding="utf-8") as f:
                batch_data = json.load(f)
            
            # Extract pages from the batch file
            pages = []
            if isinstance(batch_data, dict):
                if "pages" in batch_data:
                    pages = batch_data["pages"]
                elif "text_blocks" in batch_data:
                    # Single page JSON or legacy flat structure
                    pages = [batch_data]
                else:
                    print(f"  [WARN] Unknown structure in {bf.name}, attempting to parse as single page...")
                    pages = [batch_data]
            elif isinstance(batch_data, list):
                pages = batch_data
            
            for page in pages:
                page_num = page.get("page_num")
                if page_num is None:
                    print(f"  [WARN] Skipping page block in {bf.name} because 'page_num' is missing.")
                    continue
                
                if page_num in seen_pages:
                    print(f"  [WARN] Duplicate page {page_num} found. Overwriting with page from {bf.name}.")
                    # Remove the old one
                    merged_pages = [p for p in merged_pages if p.get("page_num") != page_num]
                
                merged_pages.append(page)
                seen_pages.add(page_num)
        
        except Exception as e:
            print(f"  [FAIL] Error reading {bf.name}: {e}")
            sys.exit(1)

    # Sort pages by page_num
    merged_pages.sort(key=lambda x: x.get("page_num", 0))

    # Verify pages
    missing_pages = [p for p in range(1, total_pages + 1) if p not in seen_pages]
    if missing_pages:
        print(f"  [WARN] The following pages are missing from extraction: {missing_pages}")
        if not force:
            print("  [FAIL] Extraction is incomplete. Use --force to merge anyway.")
            sys.exit(1)
        else:
            print("  [INFO] Proceeding anyway (--force is enabled).")
    else:
        ok(f"All {total_pages} pages extracted successfully.")

    # ── Step 2: Save to data/extracted/<uuid>.json ────────────────────────────
    step_banner(2, "Save merged JSON to standard extracted directory")
    
    final_data = {
        "source_pdf": original_filename,
        "extraction_engine": "Gemini 3.5 Flash Vision (IDE Built-in)",
        "total_pages": total_pages,
        "pages": merged_pages
    }

    json_dest = EXTRACTED_DIR / f"{file_id}.json"
    try:
        EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
        with open(json_dest, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        ok(f"Saved merged JSON -> {json_dest}")
    except Exception as e:
        fail(f"Failed to save merged JSON: {e}")
        sys.exit(1)

    # ── Step 3: Register in DB and update status ──────────────────────────────
    step_banner(3, "Update status in PostgreSQL to 'extracted'")
    db = SessionLocal()
    
    doc = repository.get_document_by_id(db, file_id)
    if not doc:
        # Fallback registration if not found (should not happen)
        print("  [WARN] Document record not found in DB. Re-creating...")
        doc = repository.create_document(
            db=db,
            file_id=file_id,
            original_filename=original_filename,
            classification=classification,
            file_path=str(temp_dir.parent / f"{file_id}.pdf") # typical location
        )

    repository.update_document_status(db, file_id, status="extracting")
    repository.update_document_status(
        db, file_id, status="extracted",
        extracted_json_path=str(json_dest)
    )
    ok("PostgreSQL status updated to 'extracted'")

    # ── Step 4: Preprocessing & Chunking ──────────────────────────────────────
    step_banner(4, "Preprocessing & Chunking")
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

    # ── Step 5: BGE Embedding ──────────────────────────────────────────────────
    step_banner(5, "BGE Embedding (bge-base-en-v1.5)")
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

    # ── Step 6: Qdrant Upsert ──────────────────────────────────────────────────
    step_banner(6, "Qdrant Upsert")
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

    # ── Step 7: Final status ───────────────────────────────────────────────────
    final_doc = repository.update_document_status(db, file_id, status="ingested")
    db.close()

    print(f"\n{DIVIDER}")
    print(f"  POST-EXTRACTION PIPELINE SUCCESS")
    print(f"  document_id     : {final_doc.id}")
    print(f"  file_id (UUID)  : {file_id}")
    print(f"  Extracted JSON  : {json_dest}")
    print(f"  Preprocessed    : {preprocessed_path}")
    print(f"  Vectors upserted: {len(embedded_chunks)}")
    print(f"  Final status    : {final_doc.status}")
    print(DIVIDER)


def main():
    parser = argparse.ArgumentParser(
        description="Post-extraction helper script"
    )
    parser.add_argument(
        "file_id",
        type=str,
        help="UUID of the document to process.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force ingestion even if some pages are missing.",
    )

    args = parser.parse_args()
    run_post_extraction(args.file_id, args.force)


if __name__ == "__main__":
    main()
