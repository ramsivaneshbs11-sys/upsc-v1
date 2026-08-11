import json, sys
from pathlib import Path

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.callout_detector import tag_callout_blocks

output_dir  = Path('outputs')
json_path   = output_dir / 'ONLY IAS - ART & CULTURE_extracted.json'
pdf_path    = Path('inputs/ONLY IAS - ART & CULTURE.pdf')

print(f"Loading {json_path.name}...")
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

text_blocks = data.get('text_blocks', [])
page_images = data.get('page_images', [])

# Clear any existing (potentially buggy) callout tags so we start fresh
for b in text_blocks:
    b.pop('highlight_type', None)
    b.pop('box_id', None)

page_renders = [p for p in page_images if p.get('type') == 'page_render']
print(f"Blocks: {len(text_blocks)} | Page renders available: {len(page_renders)}")

print("Applying fixed callout detector...")
updated_blocks = tag_callout_blocks(text_blocks, page_images, output_dir, pdf_path=pdf_path)

# Count results
tagged = [b for b in updated_blocks if b.get('highlight_type')]
import collections
by_type = collections.Counter(b.get('highlight_type') for b in tagged)
by_page = sorted(set(b.get('page_num') for b in tagged))

print(f"\n=== Fix 4 Results ===")
print(f"Total tagged blocks : {len(tagged)}")
print(f"By highlight type   : {dict(by_type)}")
print(f"Tagged pages        : {by_page[:30]}")

# Show sample tags
print("\nSample tagged blocks:")
for b in tagged[:8]:
    text = b.get('text', '')[:60].encode('ascii', errors='replace').decode('ascii')
    print(f"  [Page {b.get('page_num'):3d}] ({b.get('highlight_type')}, {b.get('box_id')}) {text!r}")

data['text_blocks'] = updated_blocks

print(f"\nSaving updated JSON to {json_path}...")
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done.")
