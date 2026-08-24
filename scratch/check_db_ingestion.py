import sys
from pathlib import Path
# Add workspace to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.database.models import Document

session = SessionLocal()
try:
    docs = session.query(Document).order_by(Document.original_filename).all()
    print(f"Total documents registered: {len(docs)}")
    print("-" * 120)
    print(f"{'Filename':<30} | {'Classification':<15} | {'Status':<12} | {'File Path'}")
    print("-" * 120)
    for d in docs:
        print(f"{d.original_filename[:30]:<30} | {d.classification:<15} | {d.status:<12} | {d.file_path}")
    print("-" * 120)
finally:
    session.close()
