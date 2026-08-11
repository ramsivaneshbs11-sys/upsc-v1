import json
import sys

# Check JSON structure
with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

print('Top-level keys:', list(art.keys()))
print('page_images count:', len(art.get('page_images', [])))

blocks = art.get('text_blocks', [])
p14 = [b for b in blocks if b.get('page_num') == 14]
print('\nPage 14 full bbox breakdown (x0, x1, width):')
for b in p14:
    bbox = b.get('bbox', [])
    x0 = bbox[0] if bbox else 0
    x1 = bbox[2] if bbox else 0
    w  = x1 - x0
    print(f'  x0={x0:6.1f}  x1={x1:6.1f}  w={w:6.1f}  type={b.get("type"):12s}  {b.get("text","")[:45]!r}')

# Check actual page width from the fitz perspective
try:
    import fitz
    doc = fitz.open('inputs/Art-and-Culture-Print-Friendly-Sample.pdf')
    p = doc[13]  # page index 13 = page_num 14
    print(f'\nPage 14 fitz rect: width={p.rect.width:.1f}  height={p.rect.height:.1f}')
    doc.close()
except Exception as e:
    print(f'fitz error: {e}')
