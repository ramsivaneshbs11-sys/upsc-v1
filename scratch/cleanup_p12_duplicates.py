import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.database.models import Document
from app.services.qdrant_service import get_qdrant_client
from app.core.config import QDRANT_COLLECTION_MAP
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Pathshala P-12 directory path
p12_dir = Path(r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-12")

def main():
    if not p12_dir.exists():
        print(f"Directory not found: {p12_dir}")
        return
        
    session = SessionLocal()
    qdrant_client = get_qdrant_client()
    
    try:
        pdf_files = sorted(list(p12_dir.glob("*.pdf")))
        pdf_names = [f.name for f in pdf_files]
        
        # Query database for these filenames
        db_docs = session.query(Document).filter(Document.original_filename.in_(pdf_names)).all()
        
        # Group records by filename
        filename_to_records = {}
        for doc in db_docs:
            filename_to_records.setdefault(doc.original_filename, []).append(doc)
            
        print(f"--- Duplicate Ingestion Cleanup for P-12 ---")
        
        total_deleted_docs = 0
        total_deleted_qdrant = 0
        
        for name in pdf_names:
            records = filename_to_records.get(name, [])
            if len(records) <= 1:
                continue # No duplicates
                
            # Sort records by created_at ascending (keep the oldest successful ingestion)
            # Find the first record that is "ingested". If none, keep the oldest one.
            records_sorted = sorted(records, key=lambda r: (r.status != 'ingested', r.created_at))
            
            # The first one is the one we want to KEEP
            keep_doc = records_sorted[0]
            remove_docs = records_sorted[1:]
            
            print(f"\nFile: {name}")
            print(f"  KEEPING: ID={keep_doc.id} | Status={keep_doc.status} | Created={keep_doc.created_at}")
            
            for del_doc in remove_docs:
                print(f"  DELETING DUPLICATE: ID={del_doc.id} | Status={del_doc.status} | Created={del_doc.created_at}")
                
                # 1. Delete from Qdrant if the collection mapping exists
                collection_name = QDRANT_COLLECTION_MAP.get(del_doc.classification)
                if collection_name:
                    try:
                        qdrant_client.delete(
                            collection_name=collection_name,
                            points_selector=Filter(
                                must=[
                                    FieldCondition(
                                        key="file_id",
                                        match=MatchValue(value=del_doc.id),
                                    )
                                ]
                            )
                        )
                        print(f"    - Cleared vectors from Qdrant collection '{collection_name}'")
                        total_deleted_qdrant += 1
                    except Exception as e:
                        print(f"    - Qdrant deletion warning: {e}")
                
                # 2. Delete from PostgreSQL
                session.delete(del_doc)
                total_deleted_docs += 1
                
        # Commit all Postgres deletions
        session.commit()
        print("\n" + "=" * 50)
        print(f"Cleanup completed successfully!")
        print(f"Total duplicate database rows deleted: {total_deleted_docs}")
        print(f"Total duplicate Qdrant point sets deleted: {total_deleted_qdrant}")
        print("=" * 50)
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error occurred during cleanup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
