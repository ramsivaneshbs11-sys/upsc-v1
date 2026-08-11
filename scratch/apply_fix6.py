"""
Apply Fix 6 (degenerate table filter) to all three existing extracted JSONs
and report what was removed/flagged.
"""
import json, sys, re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.docling_extractor import filter_degenerate_tables

jsonfiles = [
    'outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json',
    'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json',
    'outputs/ONLY IAS - ART & CULTURE_extracted.json',
]

for json_path in jsonfiles:
    p = Path(json_path)
    if not p.exists():
        print(f"SKIP (missing): {p.name}")
        continue

    with open(p, encoding='utf-8') as f:
        data = json.load(f)

    tables = data.get('tables', [])
    text_blocks = data.get('text_blocks', [])

    pre_table_count = len(tables)
    pre_block_count = len(text_blocks)

    updated_tables, updated_blocks = filter_degenerate_tables(tables, text_blocks)

    removed = pre_table_count - len(updated_tables)
    flagged = sum(1 for t in updated_tables if t.get('needs_review'))
    recovered = len(updated_blocks) - pre_block_count

    print(f"\n=== {p.name} ===")
    print(f"  Tables  : {pre_table_count} → {len(updated_tables)}  (removed={removed}, flagged={flagged})")
    print(f"  Blocks  : {pre_block_count} → {len(updated_blocks)}  (recovered={recovered})")

    # Show what was removed
    for t in tables:
        from extraction.docling_extractor import _is_degenerate_table
        is_d, reason = _is_degenerate_table(t)
        if is_d and reason in ('empty', 'single_cell'):
            rows = t.get('rows', [])
            cell_preview = str(rows[0])[:60] if rows else '(empty)'
            print(f"  REMOVED [{reason:12s}] page={t.get('page_num')} rows={t.get('row_count')} | {cell_preview!r}")

    # Show what was flagged
    for t in updated_tables:
        if t.get('needs_review'):
            print(f"  FLAGGED [needs_review] page={t.get('page_num')} rows={t.get('row_count')} headers={str(t.get('headers',[]))[:50]}")

    # Save updated JSON
    data['tables'] = updated_tables
    data['table_count'] = len(updated_tables)
    data['text_blocks'] = updated_blocks
    data['block_count'] = len(updated_blocks)

    # Re-index block IDs
    for idx, b in enumerate(updated_blocks, start=1):
        b['block_id'] = f'blk_{idx:04d}'

    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Saved   : {p.name}")

print("\nAll done.")
