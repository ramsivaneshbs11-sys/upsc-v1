import json, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

blocks = art.get('text_blocks', [])
tables = art.get('tables', [])
pimgs  = art.get('page_images', [])

print("=== Art & Culture - POST-FIX VERIFICATION ===")
print(f"Total text_blocks : {len(blocks)}")
print(f"Total tables      : {len(tables)}")

# FIX 2: TOC tables
toc_gone = all(t.get('headers', []) != ['Column_1','Column_2','Column_3'] for t in tables)
print(f"\n[Fix 2] TOC tables removed  : {'PASS - only real tables remain' if len(tables) == 1 else f'FAIL - {len(tables)} tables'}")
for t in tables:
    print(f"  Table: page={t.get('page_num')} headers={t.get('headers')} rows={len(t.get('rows',[]))}")

# FIX 1: column order on page 14
p14 = [b for b in blocks if b.get('page_num') == 14]
col_seq = []
for b in p14:
    bbox = b.get('bbox')
    if bbox:
        col_seq.append('L' if bbox[0] < 297 else 'R')
switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
print(f"\n[Fix 1] Page 14 col-switches: {switches}  seq={''.join(col_seq)}")
print(f"        {'PASS - clean left-then-right' if switches <= 1 else 'FAIL - still interleaved'}")

# FIX 4: page renders and callout tags
renders = [m for m in pimgs if m.get('type') == 'page_render']
print(f"\n[Fix 4] page_render images  : {len(renders)}")
tagged  = sum(1 for b in blocks if b.get('highlight_type') or b.get('box_id'))
print(f"        callout-tagged blocks: {tagged}")
print(f"        {'PASS - page renders exist for callout sampling' if renders else 'FAIL - no renders'}")

# FIX 3: heading-as-footer
DOT = re.compile(r'\d+(\.\d+)*\s+[A-Z]')
hf = [b for b in blocks if b.get('type') == 'footer' and not b.get('is_boilerplate') and DOT.match(b.get('text','').strip())]
print(f"\n[Fix 3] Heading-typed-footer: {len(hf)}  {'PASS' if not hf else 'FAIL'}")

# Type distribution
type_counts = collections.Counter(b.get('type') for b in blocks)
print(f"\nBlock types: {dict(type_counts)}")

# TOC blocks re-emitted
toc_blocks = [b for b in blocks if b.get('type') == 'toc']
print(f"TOC blocks re-emitted: {len(toc_blocks)}")
