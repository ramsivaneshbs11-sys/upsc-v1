"""
scratch/verify_pdf_folders.py
─────────────────────────────
Checks if PDFs in the specified folders are already ingested into PostgreSQL and Qdrant.
Generates a markdown report at scratch/folder_verification_report.md.
"""
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

# List of folders provided by the user
TARGET_FOLDERS = [
    r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-01",
    r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-02",
    r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-03",
    r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-04",
    r"C:\Users\vishn\Downloads\ANTHROPOLOGY-20260812T065301Z-1-001\ANTHROPOLOGY\Pathshala\P-05",
    str(ROOT_DIR / "P-05")
]

db = SessionLocal()
client = QdrantClient(host="localhost", port=6333)

report_lines = []
report_lines.append("# Folder Ingestion Verification Report")
report_lines.append(f"Generated on: {Path(__file__).name}")
report_lines.append("\n" + "=" * 50 + "\n")

summary_by_folder = {}

for folder_path in TARGET_FOLDERS:
    folder = Path(folder_path)
    
    # Label for display
    display_name = folder.name
    if "ANTHROPOLOGY" in folder_path:
        display_name = f"Downloads / {folder.name}"
    else:
        display_name = f"Workspace / {folder.name}"
        
    report_lines.append(f"## Scanning Folder: `{display_name}`")
    report_lines.append(f"Full Path: `{folder_path}`\n")
    
    if not folder.exists() or not folder.is_dir():
        report_lines.append("❌ **Folder does not exist on disk (Skipped).**\n")
        print(f"Skipping: Folder does not exist -> {folder_path}")
        continue
        
    # Use case-insensitive deduplication — on Windows, *.pdf and *.PDF return the same files
    seen = set()
    pdf_files = []
    for p in sorted(folder.glob("*")):
        if p.suffix.lower() == ".pdf" and p.name.lower() not in seen:
            seen.add(p.name.lower())
            pdf_files.append(p)
    report_lines.append(f"Total PDFs found in folder: **{len(pdf_files)}**\n")
    
    if not pdf_files:
        report_lines.append("No PDFs found.\n")
        continue

    folder_stats = {
        "fully_ingested": 0,
        "incomplete": 0,
        "not_ingested": 0
    }
    
    table_headers = "| # | PDF Filename | DB Status | Preprocessed | Qdrant Points | Final Status |"
    table_divider = "|---|---|---|---|---|---|"
    report_lines.append(table_headers)
    report_lines.append(table_divider)
    
    for idx, pdf in enumerate(pdf_files, 1):
        filename = pdf.name
        
        # 1. Check DB
        doc = db.query(Document).filter(Document.original_filename == filename).first()
        
        db_status = "Missing"
        prep_status = "N/A"
        qdrant_points = 0
        final_status = "❌ Not Ingested"
        
        if doc:
            db_status = doc.status
            
            # Check preprocessing JSON
            prep_exists = False
            if doc.preprocessed_json_path:
                p = Path(doc.preprocessed_json_path)
                if p.exists():
                    prep_exists = True
                else:
                    fallback = ROOT_DIR / "data" / "preprocessed" / f"{doc.id}_preprocessed.json"
                    if fallback.exists():
                        prep_exists = True
            
            prep_status = "Found" if prep_exists else "Missing"
            
            # 2. Check Qdrant
            collections_to_check = ["anthropology_collection", "history_collection"]
            for col in collections_to_check:
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
                        limit=5
                    )
                    points = res[0]
                    if len(points) > 0:
                        qdrant_points = len(points)
                        break
                except Exception:
                    pass

            if doc.status == "ingested" and prep_exists and qdrant_points > 0:
                final_status = "✅ Fully Ingested"
                folder_stats["fully_ingested"] += 1
            else:
                final_status = "⚠️ Incomplete"
                folder_stats["incomplete"] += 1
        else:
            folder_stats["not_ingested"] += 1
            
        report_lines.append(f"| {idx} | {filename} | {db_status} | {prep_status} | {qdrant_points} | {final_status} |")
        
    report_lines.append(f"\n**Folder Summary:**")
    report_lines.append(f"- Fully Ingested: **{folder_stats['fully_ingested']}**")
    report_lines.append(f"- Incomplete: **{folder_stats['incomplete']}**")
    report_lines.append(f"- Not Ingested: **{folder_stats['not_ingested']}**")
    report_lines.append("\n" + "-" * 40 + "\n")
    
    summary_by_folder[display_name] = folder_stats
    print(f"Scanned {display_name}: {folder_stats}")

db.close()

# Write markdown report
report_path = ROOT_DIR / "scratch" / "folder_verification_report.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"\nVerification report generated successfully at: {report_path}")
