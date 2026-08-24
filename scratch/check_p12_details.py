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
    pdf_names = [f.name for f in pdf_files]
    
    # Query database for these filenames
    db_docs = session.query(Document).filter(Document.original_filename.in_(pdf_names)).all()
    
    # Map original filename to database records
    filename_to_records = {}
    for doc in db_docs:
        filename_to_records.setdefault(doc.original_filename, []).append(doc)
        
    print(f"P-12 Detailed Ingestion Status:")
    print(f"Total Unique PDFs in local folder: {len(pdf_files)}")
    print("-" * 80)
    
    ingested_unique = []
    processing_unique = []
    missing_unique = []
    duplicate_info = []
    
    for f in pdf_files:
        records = filename_to_records.get(f.name, [])
        if not records:
            missing_unique.append(f.name)
        else:
            # Check if any record is ingested
            statuses = [r.status for r in records]
            if "ingested" in statuses:
                ingested_unique.append(f.name)
            else:
                processing_unique.append((f.name, statuses))
                
            if len(records) > 1:
                duplicate_info.append((f.name, len(records)))
                
    print(f"Ingested (At least once): {len(ingested_unique)} / {len(pdf_files)}")
    print(f"Processing (Not yet ingested but registered): {len(processing_unique)} / {len(pdf_files)}")
    print(f"Missing (Never registered): {len(missing_unique)} / {len(pdf_files)}")
    print("-" * 80)
    
    if missing_unique:
        print("Missing Files (Innum start aagala):")
        for m in missing_unique:
            print(f"  - {m}")
        print("-" * 80)
        
    if processing_unique:
        print("Processing Files (Odivittu irukura files):")
        for name, statuses in processing_unique:
            print(f"  - {name} (Statuses: {', '.join(statuses)})")
        print("-" * 80)
        
    if duplicate_info:
        print("WARNING: Duplicate Ingestions (Athanvazhiyaa re-ingested):")
        for name, count in duplicate_info:
            print(f"  - {name} has {count} entries in DB")
        print("-" * 80)

finally:
    session.close()
