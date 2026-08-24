import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.database.models import Document

# Pathshala directory path
pathshala_dir = Path(r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala")

session = SessionLocal()
try:
    # Get all ingested original filenames from DB
    ingested_filenames = {d.original_filename for d in session.query(Document).filter(Document.status == "ingested").all()}
    
    if not pathshala_dir.exists():
        print(f"Directory not found: {pathshala_dir}")
        sys.exit(1)
        
    print(f"Checking subdirectories in: {pathshala_dir}")
    print("-" * 80)
    
    # Sort folders (e.g. P-01, P-02, P-07, etc.)
    subdirs = sorted([d for d in pathshala_dir.iterdir() if d.is_dir()])
    
    for subdir in subdirs:
        pdf_files = list(subdir.glob("*.pdf"))
        if not pdf_files:
            continue
        
        ingested_count = sum(1 for f in pdf_files if f.name in ingested_filenames)
        total_count = len(pdf_files)
        
        status = "COMPLETE" if ingested_count == total_count else f"PENDING ({total_count - ingested_count}/{total_count} files left)"
        if ingested_count == 0:
            status = "NOT INGESTED"
            
        print(f"Folder: {subdir.name:<15} | Total PDFs: {total_count:<3} | Ingested: {ingested_count:<3} | Status: {status}")
    print("-" * 80)

finally:
    session.close()
