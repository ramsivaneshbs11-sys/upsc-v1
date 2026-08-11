"""
Deep-inspect the remaining multi-switch pages to identify if they are
truly broken (mixed L/R content from wrong column detection) or just
structural edge cases (tables, MCQ answer columns, figure captions).
"""
import json, sys, fitz, collections
from pathlib import Path
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.reorder_blocks import _detect_column_midpoint

def inspect_page(json_path, pdf_path, page_num, max_blocks=20):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    blocks = [b for b in data['text_blocks'] if b.get('page_num') == page_num]
    doc = fitz.open(pdf_path)
    pw = doc[page_num - 1].rect.width
    doc.close()
    mid = _detect_column_midpoint(blocks, pw)
    split = mid - 5.0
    col_seq = ['L' if (b.get('bbox') or [0])[0] < split else 'R' for b in blocks if b.get('bbox')]
    switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
    print(f"\n  Page {page_num} (pw={pw:.0f} mid={mid:.0f} split<{split:.0f}) sw={switches}  seq={''.join(col_seq[:25])}")
    for b in blocks[:max_blocks]:
        bbox = b.get('bbox', [0,0,0,0])
        col = 'L' if bbox[0] < split else 'R'
        text = b.get('text', '')[:55].encode('ascii', errors='replace').decode('ascii')
        tp = b.get('type','?')[:4]
        print(f"    [{col}] x0={bbox[0]:6.1f} {tp:4s} | {text!r}")

print("=== NITIN SINGHANIA bad pages ===")
for pg in [181, 276, 307]:
    inspect_page(
        'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json',
        'inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf',
        pg
    )

print("\n=== ONLY IAS bad pages ===")
for pg in [25, 29, 36]:
    inspect_page(
        'outputs/ONLY IAS - ART & CULTURE_extracted.json',
        'inputs/ONLY IAS - ART & CULTURE.pdf',
        pg
    )
