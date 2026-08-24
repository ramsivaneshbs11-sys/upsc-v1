import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.database.models import Document

# Pathshala P-12 directory path
p12_dir = Path(r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-12")

session = SessionLocal()
try:
    if not p12_dir.exists():
        print(f"Directory not found: {p12_dir}")
        sys.exit(1)
        
    pdf_files = sorted(list(p12_dir.glob("*.pdf")))
    pdf_names = {f.name for f in pdf_files}
    
    # Query database for these filenames
    db_docs = session.query(Document).filter(Document.original_filename.in_(pdf_names)).all()
    
    print(f"P-12 Ingestion Status Summary:")
    print(f"Total PDFs in folder: {len(pdf_files)}")
    print(f"Registered in Database: {len(db_docs)}")
    print("-" * 80)
    
    status_counts = {}
    doc_details = []
    
    for d in db_docs:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
        doc_details.append(f"{d.original_filename:<30} | {d.status:<12} | {d.error_message or 'No error'}")
        
    print("Status counts:")
    for status, count in status_counts.items():
        print(f"  - {status}: {count}")
    print("-" * 80)
    
    if doc_details:
        print("Details for registered files:")
        for detail in doc_details:
            print(detail)
    else:
        print("No files from P-12 are registered in the database yet.")
    print("-" * 80)

finally:
    session.close()
