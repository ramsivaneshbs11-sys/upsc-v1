import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import text

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.core.config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_MAP
from app.database.session import SessionLocal

def cleanup_document(filename: str, classification: str):
    print(f"--- CLEANING UP DOCUMENT '{filename}' ({classification}) ---")
    
    db = SessionLocal()
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    collection_name = QDRANT_COLLECTION_MAP.get(classification)
    
    if not collection_name:
        print(f"[ERROR] No Qdrant collection mapped for classification '{classification}'")
        db.close()
        return

    try:
        # 1. Query PostgreSQL for existing document records matching the filename
        sql_query = text("SELECT id, file_path FROM documents WHERE original_filename = :filename")
        rows = db.execute(sql_query, {"filename": filename}).fetchall()
        
        if not rows:
            print(f"No database records found in PostgreSQL for '{filename}'. Database is clean!")
            db.close()
            return
            
        file_ids = [r[0] for r in rows]
        file_paths = [r[1] for r in rows]
        print(f"Found {len(file_ids)} existing database record(s) with file_id(s): {file_ids}")
        
        # 2. Delete points from Qdrant matching those file_ids
        print(f"Deleting points from Qdrant collection '{collection_name}'...")
        for fid in file_ids:
            filter_cond = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="file_id",
                        match=qmodels.MatchValue(value=fid)
                    )
                ]
            )
            res = client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(filter=filter_cond)
            )
            print(f"  - Deleted chunks in Qdrant for file_id {fid}: {res}")
            
        # 3. Delete records from PostgreSQL
        print("Deleting records from PostgreSQL...")
        delete_sql = text("DELETE FROM documents WHERE original_filename = :filename")
        db.execute(delete_sql, {"filename": filename})
        db.commit()
        print("  - Deleted PostgreSQL database records OK")
        
        # 4. Clean up local files
        from app.core.config import EXTRACTED_DIR, PREPROCESSED_DIR
        for fid in file_ids:
            ext_path = EXTRACTED_DIR / f"{fid}.json"
            prep_path = PREPROCESSED_DIR / f"{fid}_preprocessed.json"
            if ext_path.exists():
                ext_path.unlink()
                print(f"  - Deleted {ext_path.name}")
            if prep_path.exists():
                prep_path.unlink()
                print(f"  - Deleted {prep_path.name}")
                
        # Clean up the actual saved PDFs in uploads
        for path_str in file_paths:
            if path_str:
                path_obj = Path(path_str)
                if path_obj.exists():
                    path_obj.unlink()
                    print(f"  - Deleted uploaded PDF file {path_obj.name}")
                    
        print(f"\n[SUCCESS] Document '{filename}' has been fully cleaned up from PostgreSQL, Qdrant, and storage!")
        
    except Exception as exc:
        print(f"[ERROR] Cleanup failed: {exc}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cleanup a document fully from databases.")
    parser.add_argument("filename", type=str, help="The original filename (e.g. 'TRIBES INDIA.pdf')")
    parser.add_argument("--classification", type=str, required=True, choices=["History", "Anthropology"])
    args = parser.parse_args()
    cleanup_document(args.filename, args.classification)
