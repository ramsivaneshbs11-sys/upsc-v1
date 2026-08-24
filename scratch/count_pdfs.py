import os
from pathlib import Path

ROOT = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main")

pdf_counts = {}
total_pdfs = 0

for root, dirs, files in os.walk(ROOT):
    # Skip standard folders we don't care about
    if any(p in root for p in [".git", "__pycache__", "venv", ".agents", ".gemini", "data"]):
        continue
    pdfs = [f for f in files if f.lower().endswith(".pdf")]
    if pdfs:
        rel_path = Path(root).relative_to(ROOT)
        pdf_counts[str(rel_path)] = len(pdfs)
        total_pdfs += len(pdfs)

print(f"Total PDFs found: {total_pdfs}")
print("\nBreakdown by folder:")
for folder, count in sorted(pdf_counts.items()):
    print(f"  {folder or '.'}: {count} PDFs")
