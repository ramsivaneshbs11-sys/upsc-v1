import json
from pathlib import Path

# Load original simulated output
with open("scratch/test_gemini_out/145793840413ET_gemini.json", "r", encoding="utf-8") as f:
    data = json.load(f)

pages = data["pages"]
dest_dir = Path("data/temp_extraction/2f98c8c1-96b8-4756-a49d-5ef18382f27c")

# Split pages into two batches
batch1 = {"pages": pages[:6]}
batch2 = {"pages": pages[6:]}

with open(dest_dir / "batch_1_6.json", "w", encoding="utf-8") as f:
    json.dump(batch1, f, indent=2, ensure_ascii=False)

with open(dest_dir / "batch_7_12.json", "w", encoding="utf-8") as f:
    json.dump(batch2, f, indent=2, ensure_ascii=False)

print("Split mock data into batches successfully!")
