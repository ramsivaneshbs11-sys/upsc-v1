import json
import subprocess
from pathlib import Path

def main():
    progress_path = Path("output/TRIBES INDIA/progress.json")
    if not progress_path.exists():
        print("[ERROR] progress.json not found!")
        return

    # Pages to re-extract using the updated Gemini prompt
    target_pages = [10, 12, 13, 14, 15, 16, 17, 18, 50, 51, 82, 83, 84, 191, 196, 198, 199, 200, 205, 206, 240, 263, 281]

    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    # Remove target pages from completed list
    extracted_pages = set(progress.get("extracted_pages", []))
    for p in target_pages:
        if p in extracted_pages:
            extracted_pages.remove(p)

    progress["extracted_pages"] = sorted(list(extracted_pages))
    progress["status"] = "in_progress"

    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    print(f"Reset {len(target_pages)} pages in progress.json. Starting Gemini extraction...")

    # Run the batch extraction script
    subprocess.run(["python", "gemini_batch_extract.py", "TRIBES INDIA.pdf"], check=True)

if __name__ == "__main__":
    main()
