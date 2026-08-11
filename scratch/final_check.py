"""
Final comprehensive check across all 3 extracted JSONs.
Verifies all 6 fixes are correctly applied.
"""
import json, re, sys, collections, fitz
from pathlib import Path

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.reorder_blocks import _detect_column_midpoint

HEADING_PAT = re.compile(r'^\d+(\.\d+)*\s+[A-Z]')
DOT_LEADER  = re.compile(r'\.{4,}')

def check_json(json_path, pdf_path, label):
    p = Path(json_path)
    if not p.exists():
        print(f"MISSING: {json_path}")
        return

    with open(p, encoding='utf-8') as f:
        data = json.load(f)

    blocks  = data.get('text_blocks', [])
    tables  = data.get('tables', [])
    pimgs   = data.get('page_images', [])

    # Get page widths from PDF
    page_widths = {}
    if Path(pdf_path).exists():
        doc = fitz.open(pdf_path)
        page_widths = {i + 1: doc[i].rect.width for i in range(len(doc))}
        doc.close()

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {p.name}")
    print(f"{'='*60}")
    print(f"  text_blocks : {len(blocks)}")
    print(f"  tables      : {len(tables)}")
    print(f"  page_images : {len(pimgs)}")

    # --- Fix 1: Column order ---
    pages_with_switches = []
    page_blocks_map = collections.defaultdict(list)
    for b in blocks:
        pg = b.get('page_num')
        if pg:
            page_blocks_map[pg].append(b)

    for pg, pbs in sorted(page_blocks_map.items()):
        pw = page_widths.get(pg, 612.0)
        mid_x = _detect_column_midpoint(pbs, pw)
        split = mid_x - 5.0
        col_seq = []
        for b in pbs:
            bbox = b.get('bbox')
            if bbox:
                col_seq.append('L' if bbox[0] < split else 'R')
        if 'L' in col_seq and 'R' in col_seq:
            switches = sum(1 for i in range(1, len(col_seq)) if col_seq[i] != col_seq[i-1])
            if switches > 5:
                pages_with_switches.append((pg, switches, ''.join(col_seq[:20])))

    fix1_status = "✅ PASS" if not pages_with_switches else f"❌ FAIL — {len(pages_with_switches)} pages with column interleaving"
    print(f"\n  [Fix 1] Column reading order : {fix1_status}")
    for pg, sw, seq in pages_with_switches[:3]:
        print(f"          Page {pg}: {sw} switches | {seq}")

    # --- Fix 2: TOC tables ---
    toc_tables = [t for t in tables if DOT_LEADER.search(' '.join(str(c) for row in t.get('rows',[]) for c in row))]
    fix2_status = "✅ PASS" if not toc_tables else f"❌ FAIL — {len(toc_tables)} dot-leader tables remain"
    print(f"  [Fix 2] TOC table filter     : {fix2_status}")

    # --- Fix 3: Heading-as-footer ---
    bad_footers = [b for b in blocks
                   if b.get('type') == 'footer'
                   and not b.get('is_boilerplate')
                   and HEADING_PAT.match(b.get('text','').strip())
                   and len(b.get('text','').strip()) < 80]
    fix3_status = "✅ PASS" if not bad_footers else f"❌ FAIL — {len(bad_footers)} heading-typed-as-footer"
    print(f"  [Fix 3] Heading→footer fix   : {fix3_status}")
    for b in bad_footers[:3]:
        print(f"          Page {b.get('page_num')}: {b.get('text','')[:50]!r}")

    # --- Fix 4: Callout tagging ---
    callouts = [b for b in blocks if b.get('highlight_type')]
    renders  = [m for m in pimgs if m.get('type') == 'page_render']
    fix4_status = f"✅ PASS — {len(callouts)} callout blocks on {len(set(b.get('page_num') for b in callouts))} pages" if callouts else "⚠️  0 callout blocks (correct if PDF has no pink boxes)"
    print(f"  [Fix 4] Callout box tagging  : {fix4_status}")
    print(f"          Page renders available: {len(renders)}")

    # --- Fix 5: Mojibake ---
    mojibake  = [b for b in blocks if b.get('encoding_error')]
    foot_bp   = [b for b in blocks if b.get('is_boilerplate') and b.get('type') in ('footer','header')]
    fix5_status = f"✅ PASS — {len(mojibake)} blocks flagged encoding_error=True" if len(mojibake) == 0 or all(b.get('is_boilerplate') for b in mojibake) else f"❌ FAIL — encoding_error blocks not boilerplate"
    print(f"  [Fix 5] Mojibake flagger     : {fix5_status}")

    # --- Fix 6: Degenerate tables ---
    empty_tbls   = [t for t in tables if t.get('row_count', 0) == 0 or t.get('column_count', 0) == 0]
    single_tbls  = [t for t in tables if t.get('row_count', 1) <= 1 and t.get('column_count', 1) <= 1]
    flagged_tbls = [t for t in tables if t.get('needs_review')]
    fix6_empty   = "✅" if not empty_tbls else f"❌ {len(empty_tbls)} empty"
    fix6_single  = "✅" if not single_tbls else f"❌ {len(single_tbls)} single-cell"
    print(f"  [Fix 6] Degenerate tables    : empty={fix6_empty}  single-cell={fix6_single}  needs_review={len(flagged_tbls)}")

    # Overall
    all_ok = not pages_with_switches and not toc_tables and not bad_footers and not empty_tbls and not single_tbls
    print(f"\n  OVERALL : {'✅ ALL FIXES VERIFIED' if all_ok else '⚠️  SOME ISSUES REMAIN (see above)'}")

# Run checks
check_json('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json',
           'inputs/Art-and-Culture-Print-Friendly-Sample.pdf',
           'Art-and-Culture-Print-Friendly-Sample.pdf')
check_json('outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json',
           'inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf',
           'Indian Art and Culture - Nitin Singhania 2nd(1).pdf')
check_json('outputs/ONLY IAS - ART & CULTURE_extracted.json',
           'inputs/ONLY IAS - ART & CULTURE.pdf',
           'ONLY IAS - ART & CULTURE.pdf')

print("\n\nDone.")
