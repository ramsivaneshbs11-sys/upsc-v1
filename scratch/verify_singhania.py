import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = 'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])
tables = data.get('tables', [])
page_images = data.get('page_images', [])

print("=== NITIN SINGHANIA EXTRACTION VERIFICATION ===")
print(f"Total Text Blocks : {len(blocks)}")
print(f"Total Tables      : {len(tables)}")
print(f"Total Page Images : {len(page_images)}")

# 1. Pink callout tags (Fix 4)
callouts = [b for b in blocks if b.get('highlight_type')]
print(f"\n[Fix 4] Total Callout Tagged Blocks: {len(callouts)}")
p59_60_callouts = [b for b in blocks if b.get('page_num') in (59, 60) and b.get('highlight_type')]
print(f"        Pages 59-60 Callout Blocks: {len(p59_60_callouts)}")
for b in p59_60_callouts[:5]:
    print(f"        - [Page {b.get('page_num')}] ({b.get('highlight_type')}, {b.get('box_id')}): {b.get('text')[:60]!r}")

# 2. Mojibake Flagging (Fix 5)
mojibake_flagged = [b for b in blocks if b.get('encoding_error')]
print(f"\n[Fix 5] Mojibake Flagged Blocks (encoding_error=True): {len(mojibake_flagged)}")
if mojibake_flagged:
    sample_text = mojibake_flagged[0].get('text', '')[:50].encode('ascii', errors='replace').decode('ascii')
    print(f"        Sample: {sample_text!r}")

# 3. TOC Table Filtering (Fix 2)
print(f"\n[Fix 2] Remaining Tables: {len(tables)}")

# 4. Heading misclassification (Fix 3)
heading_footers = [b for b in blocks if b.get('type') == 'footer' and not b.get('is_boilerplate') and 'History' in b.get('text', '')]
print(f"\n[Fix 3] Headings misclassified as footer: {len(heading_footers)}")

print("\nVerification Complete.")
