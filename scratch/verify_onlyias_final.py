import json, sys
from pathlib import Path
from PIL import Image
import numpy as np
import fitz

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.callout_detector import get_box_background_color, classify_highlight_color

json_path = Path('outputs/ONLY IAS - ART & CULTURE_extracted.json')
pdf_path  = Path('inputs/ONLY IAS - ART & CULTURE.pdf')
output_dir = Path('outputs')

with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])

pdf = fitz.open(str(pdf_path))

# Sample blocks from pages NOT currently tagged — check if they have colored backgrounds
untagged_content = [b for b in blocks
                    if not b.get('highlight_type')
                    and not b.get('is_boilerplate')
                    and b.get('bbox')
                    and b.get('type') in ('paragraph','list_item','heading')]

# Pick 3 random non-tagged pages
sample_pages = [20, 60, 100]
print("Sampling untagged blocks from pages:", sample_pages)
print()

for pg in sample_pages:
    page_blocks = [b for b in untagged_content if b.get('page_num') == pg][:5]
    if not page_blocks:
        print(f"Page {pg}: no untagged content blocks")
        continue

    page_img_path = output_dir / 'page_images' / f'page_{pg:03d}.png'
    if not page_img_path.exists():
        print(f"Page {pg}: no page image at {page_img_path}")
        continue

    fitz_page = pdf[pg - 1]
    w_pts, h_pts = fitz_page.rect.width, fitz_page.rect.height

    print(f"=== Page {pg} ===")
    for b in page_blocks:
        bbox = b.get('bbox')
        rgb = get_box_background_color(page_img_path, bbox, w_pts, h_pts)
        hl  = classify_highlight_color(rgb)
        text = b.get('text', '')[:45].encode('ascii', errors='replace').decode('ascii')
        print(f"  RGB={rgb} HL={hl} | {text!r}")
    print()

pdf.close()

# Final summary
tagged = [b for b in blocks if b.get('highlight_type')]
print(f"=== Final Summary ===")
print(f"Total blocks          : {len(blocks)}")
print(f"Total tagged callouts : {len(tagged)}")
print(f"Tagged pages          : {sorted(set(b.get('page_num') for b in tagged))}")
for b in tagged:
    text = b.get('text','')[:60].encode('ascii', errors='replace').decode('ascii')
    print(f"  [Page {b.get('page_num'):3d}] {b.get('highlight_type'):15s} | {text!r}")
