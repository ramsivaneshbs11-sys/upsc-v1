import json
import sys
from pathlib import Path

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.callout_detector import tag_callout_blocks

output_dir = Path('outputs')
json_path = output_dir / 'Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json'
pdf_path = Path('inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf')

print(f"Loading {json_path}...")
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

text_blocks = data.get('text_blocks', [])
page_images = data.get('page_images', [])

print(f"Applying callout detector over {len(text_blocks)} blocks...")
updated_blocks = tag_callout_blocks(text_blocks, page_images, output_dir, pdf_path=pdf_path)

data['text_blocks'] = updated_blocks

# Count total tagged
tagged = [b for b in updated_blocks if b.get('highlight_type')]
print(f"\nSUCCESS! Total Callout Tagged Blocks: {len(tagged)}")

p59_60_callouts = [b for b in updated_blocks if b.get('page_num') in (59, 60) and b.get('highlight_type')]
print(f"Pages 59-60 Callout Blocks: {len(p59_60_callouts)}")
for b in p59_60_callouts[:6]:
    print(f"  - [Page {b.get('page_num')}] ({b.get('highlight_type')}, {b.get('box_id')}): {b.get('text')[:60]!r}")

print(f"\nSaving updated JSON back to {json_path}...")
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done.")
