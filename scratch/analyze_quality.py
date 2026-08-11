import json, collections, re

# ── ART & CULTURE ──────────────────────────────────────────────────────────────
with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

blocks = art.get('text_blocks', [])
tables = art.get('tables', [])
meta   = art.get('metadata', {})

print("=== Art & Culture Sample ===")
print(f"Total text_blocks : {len(blocks)}")
print(f"Total tables      : {len(tables)}")
print(f"Metadata keys     : {list(meta.keys()) if isinstance(meta, dict) else meta}")

type_counts = collections.Counter(b.get('type') for b in blocks)
print(f"Block types       : {dict(type_counts)}")

bp_count = sum(1 for b in blocks if b.get('is_boilerplate'))
corr     = sum(1 for b in blocks if b.get('was_corrected'))
print(f"Boilerplate       : {bp_count}/{len(blocks)}")
print(f"was_corrected     : {corr}")

pages = sorted(set(b.get('page_num') for b in blocks if b.get('page_num') is not None))
print(f"Unique pages      : {len(pages)}  range {pages[0] if pages else '?'}-{pages[-1] if pages else '?'}")

# Callout / highlight fields
has_highlight = sum(1 for b in blocks if b.get('highlight_type') or b.get('is_callout') or b.get('box_id'))
print(f"Highlight-tagged  : {has_highlight}")

# Reading-order check on page 14 (double column)
page14 = [b for b in blocks if b.get('page_num') == 14]
print(f"\nPage 14 blocks    : {len(page14)}")
if page14:
    x0s = [b['bbox'][0] if b.get('bbox') else None for b in page14]
    left  = [x for x in x0s if x is not None and x < 280]
    right = [x for x in x0s if x is not None and x >= 280]
    print(f"  x0 < 280 (left col): {len(left)}   x0 >= 280 (right col): {len(right)}")
    # check interleaving
    col_seq = ['L' if (b.get('bbox') or [None])[0] is not None and (b.get('bbox') or [None,0])[0] < 280 else 'R'
               for b in page14 if b.get('bbox')]
    switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
    print(f"  Column switches (0=perfect, high=interleaved): {switches}")
    print(f"  Column seq (first 20): {''.join(col_seq[:20])}")
    for b in page14[:4]:
        bx = b.get('bbox', [])
        print(f"  [{b.get('type')}] x0={bx[0] if bx else '?':.1f} | {b.get('text','')[:60]!r}")

# Tables
print("\n=== Tables ===")
DOT = re.compile(r'\.{4,}')
for i, t in enumerate(tables):
    rows    = t.get('rows', [])
    headers = t.get('headers', [])
    pg      = t.get('page_num')
    dot     = sum(1 for row in rows if DOT.search(' '.join(str(c) for c in row)))
    dup_rows = 0
    for row in rows:
        cells = [str(c).strip() for c in row if str(c).strip()]
        if len(cells) >= 2 and len(set(cells)) < len(cells):
            dup_rows += 1
    print(f"  Table {i:02d}: page={pg} rows={len(rows)} dot_leader_rows={dot}/{len(rows)} dup_cell_rows={dup_rows} headers={headers[:3]}")

# ── NITIN SINGHANIA ─────────────────────────────────────────────────────────────
print("\n\n=== Nitin Singhania ===")
with open('outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json', encoding='utf-8') as f:
    ns = json.load(f)

ns_blocks = ns.get('text_blocks', [])
ns_tables = ns.get('tables', [])
ns_meta   = ns.get('metadata', {})

print(f"Total text_blocks : {len(ns_blocks)}")
print(f"Total tables      : {len(ns_tables)}")

ns_types = collections.Counter(b.get('type') for b in ns_blocks)
print(f"Block types       : {dict(ns_types)}")

ns_bp   = sum(1 for b in ns_blocks if b.get('is_boilerplate'))
ns_corr = sum(1 for b in ns_blocks if b.get('was_corrected'))
print(f"Boilerplate       : {ns_bp}/{len(ns_blocks)}")
print(f"was_corrected     : {ns_corr}")

ns_pages = sorted(set(b.get('page_num') for b in ns_blocks if b.get('page_num') is not None))
print(f"Unique pages      : {len(ns_pages)}  range {ns_pages[0] if ns_pages else '?'}-{ns_pages[-1] if ns_pages else '?'}")

ns_highlight = sum(1 for b in ns_blocks if b.get('highlight_type') or b.get('is_callout') or b.get('box_id'))
print(f"Highlight-tagged  : {ns_highlight}")

# Footer encoding check
footers = [b for b in ns_blocks if b.get('type') == 'footer']
mojibake = [b for b in footers if b.get('text') and any(ord(c) < 32 or (128 <= ord(c) <= 159) for c in b.get('text',''))]
print(f"Footer blocks     : {len(footers)}")
print(f"Mojibake footers  : {len(mojibake)}")
if mojibake:
    sample_txt = mojibake[0].get('text','')[:80].encode('ascii', errors='replace').decode('ascii')
    print(f"  Sample: {sample_txt!r}")

# Pages 59-60 callout check
p59_60 = [b for b in ns_blocks if b.get('page_num') in (59, 60)]
print(f"\nPages 59-60 blocks: {len(p59_60)}")
indus = [b for b in p59_60 if 'Indus' in b.get('text','') or 'Harappa' in b.get('text','') or 'Mohenjo' in b.get('text','')]
print(f"  Indus/Harappa blocks: {len(indus)}")
for b in indus[:5]:
    print(f"  [{b.get('type')}] hl={b.get('highlight_type')} | {b.get('text','')[:70]!r}")

# Heading-as-footer check
heading_pattern = re.compile(r'^\d+(\.\d+)*\s+[A-Z]')
heading_footers = [b for b in ns_blocks if b.get('type') == 'footer' and heading_pattern.match(b.get('text','').strip()) and len(b.get('text','').strip()) < 80]
print(f"\nHeading-typed-as-footer: {len(heading_footers)}")
for b in heading_footers[:5]:
    print(f"  page={b.get('page_num')} text={b.get('text','')[:60]!r}")

# Reading-order check on a double-column page
sample_page = 70  # adjust as needed
pXX = [b for b in ns_blocks if b.get('page_num') == sample_page]
if pXX:
    col_seq = []
    for b in pXX:
        bx = b.get('bbox')
        if bx:
            col_seq.append('L' if bx[0] < 280 else 'R')
    switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
    print(f"\nPage {sample_page} col-switches: {switches}  seq: {''.join(col_seq[:20])}")

print("\nDone.")
