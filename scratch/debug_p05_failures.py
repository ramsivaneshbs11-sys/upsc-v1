import os
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

print("=" * 80)
print("Listing all unique file_ids and pdf_names in anthropology_collection:")
print("=" * 80)

# Scroll all points in anthropology_collection
offset = None
unique_files = {}

try:
    while True:
        res = client.scroll(
            collection_name="anthropology_collection",
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        points, next_offset = res
        for p in points:
            payload = p.payload or {}
            fid = payload.get("file_id")
            pdf_name = payload.get("pdf_name")
            if fid:
                if fid not in unique_files:
                    unique_files[fid] = {
                        "pdf_name": pdf_name,
                        "count": 0
                    }
                unique_files[fid]["count"] += 1
        if not next_offset:
            break
        offset = next_offset

    for fid, info in unique_files.items():
        print(f"File ID in Qdrant: {fid} | PDF Name: {info['pdf_name']} | Chunks/Points count: {info['count']}")
except Exception as e:
    print(f"Error reading anthropology_collection: {e}")

db.close()
