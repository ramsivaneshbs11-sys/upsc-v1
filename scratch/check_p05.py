import os
import sys
from pathlib import Path

# Add workspace root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.session import SessionLocal
from app.database.models import Document
from qdrant_client import QdrantClient

# Path to the P-05 directory
P05_DIR = Path(r"C:\Users\vishn\Downloads\RAG-main\RAG-main\P-05")
files = sorted([f.name for f in P05_DIR.glob("*.pdf")])

db = SessionLocal()
client = QdrantClient(host="localhost", port=6333)

print("=" * 70)
print(f"VERIFYING P-05 INGESTION (Total: {len(files)} files)")
print("=" * 70)

success_count = 0

for idx, fname in enumerate(files, 1):
    doc = db.query(Document).filter(Document.original_filename == fname).first()
    
    if not doc:
        print(f"[{idx:02d}] ❌ {fname} -> Missing from PostgreSQL DB")
        continue

    # 1. Check PostgreSQL Status
    pg_ok = doc.status == "ingested"
    
    # 2. Check Preprocessing JSON exists
    prep_exists = False
    if doc.preprocessed_json_path:
        prep_exists = Path(doc.preprocessed_json_path).exists()

    # 3. Check Qdrant Vectors Ingestion
    qdrant_ok = False
    vector_count = 0
    try:
        # Search Qdrant points with filter matching doc.id (which is file_id in payload)
        from qdrant_client.http import models
        res = client.scroll(
            collection_name="anthropology_collection",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="file_id",
                        match=models.MatchValue(value=str(doc.id))
                    )
                ]
            ),
            limit=100
        )
        points = res[0]
        vector_count = len(points)
        qdrant_ok = vector_count > 0
    except Exception as e:
        pass

    if pg_ok and prep_exists and qdrant_ok:
        print(f"[{idx:02d}] ✅ {fname} -> Fully Ingested! (PostgreSQL: {doc.status} | Preprocessed File: Found | Qdrant: {vector_count} points)")
        success_count += 1
    else:
        print(
            f"[{idx:02d}] ⚠️ {fname} -> INCOMPLETE!\n"
            f"     - PostgreSQL Status  : {doc.status} {'(OK)' if pg_ok else '(FAIL)'}\n"
            f"     - Preprocessed File  : {'Found' if prep_exists else 'Missing'}\n"
            f"     - Qdrant Vectors     : {vector_count} points {'(OK)' if qdrant_ok else '(FAIL)'}"
        )

db.close()

print("=" * 70)
if success_count == len(files):
    print(f"🎉 SUCCESS! All {len(files)} files are 100% processed and active in Qdrant!")
else:
    print(f"⚠️ Warning: Only {success_count} / {len(files)} are fully active.")
print("=" * 70)
