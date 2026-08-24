import json
from pathlib import Path

progress_path = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\output\TRIBES INDIA\progress.json")
output_dir = progress_path.parent

pages_to_reset = [12, 13, 14, 15, 16, 17, 18, 191, 196, 198, 199, 200, 205]

if progress_path.exists():
    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)
    
    extracted = progress.get("extracted_pages", [])
    # Filter out target pages
    new_extracted = [p for p in extracted if p not in pages_to_reset]
    progress["extracted_pages"] = new_extracted
    
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)
    
    print(f"Updated progress.json: removed {len(extracted) - len(new_extracted)} pages.")
else:
    print("progress.json not found!")

# Delete individual page JSON files
for p in pages_to_reset:
    page_file = output_dir / f"page_{p:04d}.json"
    if page_file.exists():
        page_file.unlink()
        print(f"Deleted: {page_file.name}")
