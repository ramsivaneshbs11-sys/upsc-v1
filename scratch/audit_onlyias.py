import json, sys, re, collections
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = r'outputs/ONLY IAS - ART & CULTURE_extracted.json'
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks  = data.get('text_blocks', [])
tables  = data.get('tables', [])
pimgs   = data.get('page_images', [])

print("=== ONLY IAS ART & CULTURE — PRE-FIX AUDIT ===")
print(f"Total text_blocks : {len(blocks)}")
print(f"Total tables      : {len(tables)}")
print(f"Total page_images : {len(pimgs)}")

# Types
type_counts = collections.Counter(b.get('type') for b in blocks)
print(f"Block types       : {dict(type_counts)}")

# Boilerplate
bp = sum(1 for b in blocks if b.get('is_boilerplate'))
print(f"Boilerplate blocks: {bp}")

# Page coverage
pages = sorted(set(b.get('page_num') for b in blocks if b.get('page_num') is not None))
print(f"Page range        : {pages[0] if pages else '?'} – {pages[-1] if pages else '?'}  ({len(pages)} unique pages)")

# Highlight tagged
hl = sum(1 for b in blocks if b.get('highlight_type') or b.get('box_id'))
print(f"Highlight-tagged  : {hl}")

# page_render images
renders = [p for p in pimgs if p.get('type') == 'page_render']
print(f"Page renders      : {len(renders)}")

# Fix 2: TOC tables
DOT = re.compile(r'\.{4,}')
print(f"\n=== TABLE AUDIT ({len(tables)} tables) ===")
for i, t in enumerate(tables):
    rows = t.get('rows', [])
    dot  = sum(1 for row in rows if DOT.search(' '.join(str(c) for c in row)))
    dup_rows = 0
    for row in rows:
        cells = [str(c).strip() for c in row if str(c).strip()]
        if len(cells) >= 2 and len(set(cells)) < len(cells):
            dup_rows += 1
    is_toc = (dot / len(rows) > 0.5 if rows else False) or (dup_rows / len(rows) > 0.4 if rows else False)
    print(f"  Table {i:02d}: page={t.get('page_num')} rows={len(rows)} dot={dot} dup={dup_rows} is_toc={is_toc} headers={t.get('headers', [])[:3]}")

# Fix 1: reading order — check a mid-book page
sample_pages = [p for p in pages if p > 5][:5]
print(f"\n=== COLUMN ORDER CHECK (pages {sample_pages}) ===")
import fitz
from pathlib import Path

# find PDF
pdf_candidates = list(Path('inputs').rglob('*ONLY*IAS*')) + list(Path('inputs').rglob('*Art*Culture*'))
print(f"Candidate PDFs: {[str(p) for p in pdf_candidates[:5]]}")

# Fix 5: mojibake footers
footers = [b for b in blocks if b.get('type') == 'footer']
mojibake = [b for b in footers if b.get('text') and
            sum(1 for ch in b.get('text','') if not ch.isprintable() or ch == '\ufffd' or ord(ch) >= 0x80) / max(len(b.get('text','')),1) >= 0.3]
print(f"\n=== FIX 5 ===")
print(f"Footer blocks     : {len(footers)}")
print(f"Mojibake footers  : {len(mojibake)}")
if mojibake:
    sample = mojibake[0].get('text','')[:60].encode('ascii', errors='replace').decode('ascii')
    print(f"  Sample          : {sample!r}")

# Fix 3: heading-as-footer
HP = re.compile(r'^\d+(\.\d+)*\s+[A-Z]')
hf = [b for b in blocks if b.get('type') == 'footer' and not b.get('is_boilerplate') and HP.match(b.get('text','').strip()) and len(b.get('text','').strip()) < 80]
print(f"\n=== FIX 3 ===")
print(f"Headings typed as footer: {len(hf)}")
for b in hf[:5]:
    print(f"  page={b.get('page_num')} | {b.get('text','')[:60]!r}")
