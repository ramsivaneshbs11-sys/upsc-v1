import sys
import json
from pathlib import Path

# Add workspace root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.session import SessionLocal
from app.database.models import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models

db = SessionLocal()
client = QdrantClient(host="localhost", port=6333)

fname = "145793840413ET.pdf"
doc = db.query(Document).filter(Document.original_filename == fname).first()

if not doc:
    print(f"Document {fname} not found in DB!")
    db.close()
    sys.exit(1)

print("=" * 80)
print(f"File: {fname}")
print(f"DB ID: {doc.id}")
print(f"DB Status: {doc.status}")
print(f"Error Message: {doc.error_message}")
print(f"Preprocessed Json Path: {doc.preprocessed_json_path}")

# Load preprocessed json and count chunks
prep_path = Path(doc.preprocessed_json_path) if doc.preprocessed_json_path else None
if prep_path and not prep_path.exists():
    # Try fallback
    prep_path = ROOT_DIR / "data" / "preprocessed" / f"{doc.id}_preprocessed.json"

if prep_path and prep_path.exists():
    with open(prep_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = data.get("chunks", [])
    print(f"Preprocessed file has {len(chunks)} chunks.")
else:
    print("Preprocessed JSON file does not exist!")

# Count all points in Qdrant
collections = ["anthropology_collection", "history_collection"]
for col in collections:
    try:
        res = client.scroll(
            collection_name=col,
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
        print(f"Points in Qdrant '{col}': {len(points)}")
    except Exception as e:
        print(f"Error querying {col}: {e}")

db.close()
