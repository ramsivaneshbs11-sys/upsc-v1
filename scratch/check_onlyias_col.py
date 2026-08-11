import json, sys, collections
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = r'outputs/ONLY IAS - ART & CULTURE_extracted.json'
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])

# Check column order on a few content pages (not TOC/front matter)
import fitz
pdf = fitz.open('inputs/ONLY IAS - ART & CULTURE.pdf')
total_pages = len(pdf)
pdf.close()
print(f"Total PDF pages: {total_pages}")

check_pages = [30, 50, 80, 100, 120]
for pg in check_pages:
    page_blocks = [b for b in blocks if b.get('page_num') == pg]
    if not page_blocks:
        continue
    col_seq = []
    for b in page_blocks:
        bbox = b.get('bbox')
        if bbox:
            col_seq.append('L' if bbox[0] < 297 else 'R')
    switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
    print(f"Page {pg:3d}: {len(page_blocks):3d} blocks | switches={switches} | seq={''.join(col_seq[:25])}")

# Show sample from a double-column page
pg = 80
p80 = [b for b in blocks if b.get('page_num') == pg]
if p80:
    print(f"\nPage {pg} block detail:")
    for b in p80[:10]:
        bbox = b.get('bbox', [])
        x0 = bbox[0] if bbox else 0
        col = 'L' if x0 < 297 else 'R'
        text = b.get('text', '')[:50].encode('ascii', errors='replace').decode('ascii')
        print(f"  [{col}] x0={x0:6.1f} | {text!r}")

# Verify existing callout tags
tagged = [b for b in blocks if b.get('highlight_type')]
print(f"\nExisting highlight_type tags: {len(tagged)}")
by_type = collections.Counter(b.get('highlight_type') for b in tagged)
print(f"By type: {dict(by_type)}")
by_page = sorted(set(b.get('page_num') for b in tagged))
print(f"On pages: {by_page[:20]}")
