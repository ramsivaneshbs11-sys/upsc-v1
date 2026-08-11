"""
Diagnose Fix 1 column reorder failure.
Simulate what reorder_page_blocks does on page 14 of Art & Culture.
"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

blocks = art.get('text_blocks', [])
p14 = [b for b in blocks if b.get('page_num') == 14]

# From fitz: page 14 is A4-ish
# Let's check what page_width reorder_all_pages would use
import fitz
doc = fitz.open('inputs/Art-and-Culture-Print-Friendly-Sample.pdf')
page_widths = {i+1: doc[i].rect.width for i in range(len(doc))}
doc.close()

pw = page_widths.get(14, 612.0)
mid_x = pw / 2
margin = 20.0

print(f"Page 14: page_width={pw:.1f}  mid_x={mid_x:.1f}  margin={margin}")
print(f"Split threshold: x0 < {mid_x - margin:.1f} -> LEFT,  x0 >= {mid_x - margin:.1f} -> RIGHT")
print()

# Simulate is_full_width check
def is_full_width(b):
    bbox = b.get('bbox')
    if not bbox or len(bbox) < 4:
        return False
    return (bbox[2] - bbox[0]) > 0.7 * pw

# Pre-sort by descending y (top-y in Docling = bbox[1] high = top)
sorted_blocks = sorted(p14, key=lambda b: -(b.get('bbox') or [0,0,0,0])[1])

print("All blocks on page 14 after pre-sort, with column assignment:")
for b in sorted_blocks:
    bbox = b.get('bbox', [0,0,0,0])
    x0, y1 = bbox[0], bbox[1]
    fw = is_full_width(b)
    if fw:
        col = "FULL-WIDTH"
    elif x0 < mid_x - margin:
        col = "LEFT"
    else:
        col = "RIGHT"
    print(f"  col={col:10s}  x0={x0:6.1f}  y1={y1:6.1f}  fw={fw}  {b.get('text','')[:45]!r}")

# Now find the gap between x0 values to detect true midpoint
x0s = [b['bbox'][0] for b in p14 if b.get('bbox') and not is_full_width(b)]
x0s_sorted = sorted(set(round(x,0) for x in x0s))
print(f"\nDistinct x0 values (non-full-width): {x0s_sorted}")
print(f"Page width 30-70% range: {pw*0.3:.0f}–{pw*0.7:.0f}")

best_gap = 0
best_mid = pw / 2
for i in range(len(x0s_sorted)-1):
    a, b_val = x0s_sorted[i], x0s_sorted[i+1]
    gap = b_val - a
    mid_candidate = (a + b_val) / 2
    if pw*0.3 <= mid_candidate <= pw*0.7 and gap > best_gap:
        best_gap = gap
        best_mid = mid_candidate
    print(f"  gap between {a} and {b_val}: {gap:.1f}  mid={mid_candidate:.1f}")

print(f"\nAuto-detected mid_x: {best_mid:.1f} (gap={best_gap:.1f})")
print(f"With margin=5: LEFT if x0 < {best_mid-5:.1f}, RIGHT if x0 >= {best_mid-5:.1f}")
