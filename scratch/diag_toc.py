"""
Diagnose why filter_toc_tables is not removing TOC tables.
Tests _is_toc_like_table against the actual table data.
"""
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_DOT_LEADER_RE = re.compile(r"\.{4,}")

def _is_toc_like_table(table):
    rows = table.get("rows", [])
    if not rows:
        return False
    total = len(rows)
    dot_leader_hits = 0
    duplicate_cell_rows = 0
    for row in rows:
        row_text = " ".join(str(c) for c in row)
        if _DOT_LEADER_RE.search(row_text):
            dot_leader_hits += 1
        cells = [str(c).strip() for c in row if str(c).strip()]
        if len(cells) >= 2 and len(set(cells)) < len(cells):
            duplicate_cell_rows += 1
    return (dot_leader_hits / total > 0.5) or (duplicate_cell_rows / total > 0.4)

with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

tables = art.get('tables', [])
print(f"Total tables in JSON: {len(tables)}")
print()
for i, t in enumerate(tables):
    rows = t.get('rows', [])
    verdict = _is_toc_like_table(t)
    pg = t.get('page_num')
    # Show first row raw
    first_row = rows[0] if rows else []
    print(f"Table {i:02d} (page {pg}): is_toc={verdict}  rows={len(rows)}")
    if rows:
        print(f"  row[0] type={type(first_row).__name__}: {str(first_row)[:100]!r}")
