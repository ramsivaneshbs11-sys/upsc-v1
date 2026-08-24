import json
from pathlib import Path

def heal_progress():
    output_dir = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\output\TRIBES INDIA")
    progress_path = output_dir / "progress.json"

    if not progress_path.exists():
        print(f"[ERROR] progress.json not found at {progress_path}")
        return

    # Load progress.json
    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    extracted_pages = progress.get("extracted_pages", [])
    print(f"Original extracted_pages count in progress.json: {len(extracted_pages)}")

    # Check which files actually exist
    existing_pages = set()
    for f in output_dir.glob("page_*.json"):
        try:
            page_num = int(f.stem.split("_")[1])
            existing_pages.add(page_num)
        except (ValueError, IndexError):
            continue

    print(f"Actual page_XXXX.json files on disk: {len(existing_pages)}")

    # Identify missing pages that are marked as extracted
    missing_from_disk = [p for p in extracted_pages if p not in existing_pages]
    print(f"Pages marked as extracted but missing from disk ({len(missing_from_disk)}): {missing_from_disk}")

    if not missing_from_disk:
        print("[SUCCESS] No missing page files detected. Everything is in sync!")
        return

    # Filter extracted_pages list
    new_extracted_pages = [p for p in extracted_pages if p in existing_pages]
    progress["extracted_pages"] = sorted(new_extracted_pages)
    progress["status"] = "in_progress"

    # Save progress.json back
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    print(f"\n[HEALED] progress.json has been updated:")
    print(f"  - New extracted pages count: {len(new_extracted_pages)}")
    print(f"  - Status set to: 'in_progress'")
    print(f"  - Next run will process these missing pages: {missing_from_disk}")
    print("\nRun the extraction script again to capture them:")
    print("  python gemini_batch_extract.py \"TRIBES INDIA.pdf\"")

if __name__ == "__main__":
    heal_progress()
