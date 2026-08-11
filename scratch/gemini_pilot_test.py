"""Quick 3-page Gemini extraction test on the NCERT scanned PDF."""
import sys, logging
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

from pathlib import Path
from extraction.gemini_extractor import extract_with_gemini_flash

pdf = Path("inputs/[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf")
out = Path("outputs")

print("=" * 60)
print("  GEMINI FLASH — 3-PAGE PILOT TEST")
print("=" * 60)

# Extract only pages 5-7 as a pilot (skip cover/blank first pages)
_, data = extract_with_gemini_flash(pdf, out, start_page=5, end_page=7)

blocks = data['text_blocks']
print(f"\nBlocks extracted: {len(blocks)}")
print(f"Tables found   : {data['table_count']}")
print("\nSample blocks:")
for b in blocks[:8]:
    print(f"  [{b['type']:12s}] p{b['page_num']:03d}: {b['text'][:70]!r}")

print("\n✅ Pilot test complete — ready to run full document.")
