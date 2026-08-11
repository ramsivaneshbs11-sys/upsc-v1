"""
Audit ONLY IAS Art & Culture JSON for all 4 issues in only-ias-art-culture-issues.md:
Issue 1: Page content collapsing into single blob
Issue 2: PYQ boxes typed as boilerplate footer
Issue 3: Pages completely missing from extraction
Issue 4: blank_page flag on pages that have tables
"""
import json, sys, re, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = r'outputs/ONLY IAS - ART & CULTURE_extracted.json'
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])
tables = data.get('tables', [])

# Group by page
by_page   = collections.defaultdict(list)
tbl_pages = collections.defaultdict(list)
for b in blocks:
    by_page[b.get('page_num')].append(b)
for t in tables:
    tbl_pages[t.get('page_num')].append(t)

total_pages = max(max(by_page.keys() or [0]), max(tbl_pages.keys() or [0]))

print(f"Total pages in JSON : {total_pages}")
print(f"Total text_blocks   : {len(blocks)}")
print(f"Total tables        : {len(tables)}")

# ─── Issue 1: Collapsed blobs ────────────────────────────────────────────────
print("\n=== ISSUE 1: Page content collapsing into single blob ===")
collapsed_pages = []
for pg in range(1, total_pages + 1):
    pbs = by_page.get(pg, [])
    non_bp = [b for b in pbs if not b.get('is_boilerplate')]
    big_blobs = [b for b in non_bp if b.get('type') == 'paragraph' and len(b.get('text','')) > 400]
    if len(non_bp) <= 3 and big_blobs:
        collapsed_pages.append((pg, len(non_bp), max(len(b.get('text','')) for b in big_blobs)))

print(f"Collapsed blob pages: {len(collapsed_pages)}")
print(f"Sample collapsed pages: {collapsed_pages[:10]}")
# Show the worst offenders
for pg, nb, maxlen in sorted(collapsed_pages, key=lambda x: -x[2])[:5]:
    pbs = by_page.get(pg, [])
    non_bp = [b for b in pbs if not b.get('is_boilerplate')]
    text_preview = next((b.get('text','')[:100] for b in non_bp if len(b.get('text','')) > 400), '')
    print(f"  Page {pg}: {nb} blocks, max_text_len={maxlen}")
    print(f"    Preview: {text_preview!r}")

# ─── Issue 2: PYQ as boilerplate footer ──────────────────────────────────────
print("\n=== ISSUE 2: PYQ boxes misclassified as boilerplate footer ===")
PYQ_MARKERS = re.compile(r'^(Q[\.\s]|PREVIOUS YEAR QUESTION|With reference|Consider the following|Which|How many|What is)', re.IGNORECASE)
pyq_footer = [b for b in blocks if b.get('type') == 'footer' and b.get('is_boilerplate') and PYQ_MARKERS.match(b.get('text','').strip())]
print(f"PYQ-pattern blocks typed as boilerplate footer: {len(pyq_footer)}")
for b in pyq_footer[:5]:
    print(f"  Page {b.get('page_num')}: {b.get('text','')[:80]!r}")

# ─── Issue 3: Missing pages ────────────────────────────────────────────────
print("\n=== ISSUE 3: Pages completely missing from extraction ===")
all_pages_with_content = set(by_page.keys()) | set(tbl_pages.keys())
# Pages expected: 1..total_pages
# Blank pages
blank_pages = [b.get('page_num') for b in blocks if b.get('type') == 'blank_page']
missing_pages = []
for pg in range(1, total_pages + 1):
    has_text  = bool(by_page.get(pg))
    has_table = bool(tbl_pages.get(pg))
    if not has_text and not has_table:
        missing_pages.append(pg)

print(f"Completely empty pages (no text_blocks, no tables): {len(missing_pages)}")
print(f"Missing pages: {missing_pages[:20]}")

# ─── Issue 4: blank_page flag on pages with tables ───────────────────────────
print("\n=== ISSUE 4: blank_page flag on pages that have tables ===")
wrong_blank = []
for pg in range(1, total_pages + 1):
    pbs = by_page.get(pg, [])
    has_blank_block = any(b.get('type') == 'blank_page' for b in pbs)
    has_table = bool(tbl_pages.get(pg))
    if has_blank_block and has_table:
        wrong_blank.append(pg)

print(f"Pages wrongly flagged blank_page despite having tables: {len(wrong_blank)}")
print(f"Pages: {wrong_blank}")
