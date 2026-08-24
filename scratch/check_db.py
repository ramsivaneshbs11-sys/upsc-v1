import sys
from pathlib import Path

# Add workspace root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.session import SessionLocal
from app.database.models import Document

db = SessionLocal()
try:
    docs = db.query(Document).all()
    print(f"Total documents registered: {len(docs)}")
    for d in docs:
        print(f"ID: {d.id} | Name: {d.original_filename} | Status: {d.status} | Class: {d.classification}")
except Exception as e:
    print(f"Failed to query database: {e}")
finally:
    db.close()

