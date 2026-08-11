"""
Diagnose Fix 1 failures: pages 181/276/307 (Nitin Singhania) and pages 10/11/13 (ONLY IAS).
Checks auto-detected mid_x vs actual block distribution.
"""
import json, sys, fitz
from pathlib import Path
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.reorder_blocks import _detect_column_midpoint

def inspect_page(json_path, pdf_path, page_num):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    blocks = data.get('text_blocks', [])
    p_blocks = [b for b in blocks if b.get('page_num') == page_num]

    doc = fitz.open(pdf_path)
    pw = doc[page_num - 1].rect.width
    doc.close()

    mid_x = _detect_column_midpoint(p_blocks, pw)
    margin = 5.0
    split = mid_x - margin

    print(f"\n--- Page {page_num} (pw={pw:.0f}, auto-mid={mid_x:.1f}, split<{split:.1f}) ---")
    for b in p_blocks:
        bbox = b.get('bbox', [0,0,0,0])
        x0 = bbox[0]
        col = 'L' if x0 < split else 'R'
        text = b.get('text', '')[:45].encode('ascii', errors='replace').decode('ascii')
        print(f"  [{col}] x0={x0:6.1f} | {text!r}")

print("=== NITIN SINGHANIA ===")
ns_json = 'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json'
ns_pdf  = 'inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf'
for pg in [181, 276, 307]:
    inspect_page(ns_json, ns_pdf, pg)

print("\n=== ONLY IAS ===")
oi_json = 'outputs/ONLY IAS - ART & CULTURE_extracted.json'
oi_pdf  = 'inputs/ONLY IAS - ART & CULTURE.pdf'
for pg in [10, 11, 13]:
    inspect_page(oi_json, oi_pdf, pg)
