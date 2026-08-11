"""
Verify Fix 1 with the new auto-detection logic.
Simulate reorder_page_blocks on page 14 of Art & Culture.
"""
import sys, json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.reorder_blocks import reorder_page_blocks, _detect_column_midpoint

with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

blocks = art.get('text_blocks', [])
p14 = [b for b in blocks if b.get('page_num') == 14]

page_width = 612.0  # from fitz

# Test auto-detection
detected_mid = _detect_column_midpoint(p14, page_width)
print(f"Auto-detected mid_x: {detected_mid:.1f} (page_width={page_width})")
print(f"Column split: x0 < {detected_mid - 5:.1f} -> LEFT,  x0 >= {detected_mid - 5:.1f} -> RIGHT")
print()

# Run reorder
ordered = reorder_page_blocks(p14, page_width)
print("Reordered page 14 blocks:")
for b in ordered:
    bbox = b.get('bbox', [0,0,0,0])
    x0 = bbox[0]
    col = 'L' if x0 < detected_mid - 5 else 'R'
    text = b.get('text', '')[:50].encode('ascii', errors='replace').decode('ascii')
    print(f"  [{col}] x0={x0:6.1f}  {text!r}")

# Check column-switches in new order
col_seq = []
for b in ordered:
    bbox = b.get('bbox')
    if bbox:
        col_seq.append('L' if bbox[0] < detected_mid - 5 else 'R')
switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
print(f"\nColumn switches: {switches}  (was 7 before fix, should be 1)")
print(f"Sequence: {''.join(col_seq)}")
