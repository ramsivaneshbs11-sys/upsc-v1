"""
Apply Fix 7 (PYQ rescue) and Fix 8 (blank_page cross-check) to the
existing ONLY IAS JSON immediately, without re-running full extraction.
Issues 1 and 3 (blob collapse, missing pages) still require a full re-extraction.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.docling_extractor import fix_pyq_misclassification, fix_blank_page_flag

json_path = Path('outputs/ONLY IAS - ART & CULTURE_extracted.json')

with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])
tables = data.get('tables', [])

pre_pyq_count  = sum(1 for b in blocks if b.get('type') == 'footer' and b.get('is_boilerplate'))
pre_blank_count = sum(1 for b in blocks if b.get('type') == 'blank_page')

# Apply Fix 7
blocks = fix_pyq_misclassification(blocks)

# Apply Fix 8
blocks = fix_blank_page_flag(blocks, tables)

# Re-index
for idx, b in enumerate(blocks, start=1):
    b['block_id'] = f'blk_{idx:04d}'

post_pyq_rescued = sum(1 for b in blocks if b.get('type') == 'pyq_question')
post_blank_count = sum(1 for b in blocks if b.get('type') == 'blank_page')

print(f"=== Fix 7 — PYQ Rescue ===")
print(f"  Before: {pre_pyq_count} boilerplate footer blocks")
print(f"  PYQ blocks now rescued as pyq_question: {post_pyq_rescued}")
print(f"\nSample PYQ rescued blocks:")
for b in [b for b in blocks if b.get('type') == 'pyq_question'][:5]:
    print(f"  [Page {b.get('page_num'):3d}] {b.get('text','')[:70]!r}")

print(f"\n=== Fix 8 — Blank Page Cross-check ===")
print(f"  Before: {pre_blank_count} blank_page blocks")
print(f"  After : {post_blank_count} blank_page blocks")
print(f"  Removed: {pre_blank_count - post_blank_count} spurious blank_page blocks")

# Save
data['text_blocks'] = blocks
data['block_count'] = len(blocks)
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nSaved: {json_path.name}")
