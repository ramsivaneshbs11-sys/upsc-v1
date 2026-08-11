"""
Extraction Quality Reviewer — ONLY IAS Art & Culture
Evaluates extraction quality across 8 dimensions as per the QA prompt.
"""
import json, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = Path('outputs/ONLY IAS - ART & CULTURE_extracted.json')
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

blocks  = data.get('text_blocks', [])
tables  = data.get('tables', [])
total_pages = max((b.get('page_num', 0) for b in blocks), default=0)

issues = []  # (type, desc, severity, fix)

# ─── 1. SEQUENCE & ORDER ─────────────────────────────────────────────────────
by_page = collections.defaultdict(list)
for b in blocks:
    pg = b.get('page_num')
    if pg:
        by_page[pg].append(b)

out_of_order = 0
for pg, pbs in sorted(by_page.items()):
    bboxes = [b.get('bbox') for b in pbs if b.get('bbox')]
    if len(bboxes) < 2:
        continue
    ys = [bb[1] for bb in bboxes]  # y0 (top)
    drops = sum(1 for i in range(1, len(ys)) if ys[i] < ys[i-1] - 20)
    if drops > 2:
        out_of_order += 1

if out_of_order > 0:
    issues.append((
        "Sequence & Order",
        f"{out_of_order} pages have blocks with non-monotonic y-coordinates (may indicate column-sort artefacts after restructuring)",
        "Low",
        "Run column-aware reorder_all_pages() pass post dict-restructuring"
    ))
else:
    print("[1] Sequence & Order: ✅ PASS")

# ─── 2. COMPLETENESS ─────────────────────────────────────────────────────────
empty_pages = [pg for pg in range(1, total_pages+1) if not by_page.get(pg)]
if empty_pages:
    issues.append((
        "Completeness",
        f"{len(empty_pages)} pages have zero text blocks: {empty_pages[:10]}",
        "High",
        "Trigger fitz fallback for empty pages"
    ))
else:
    print("[2] Completeness: ✅ PASS (all pages have content)")

# ─── 3. CONTINUITY ────────────────────────────────────────────────────────────
mid_sentence_ends = 0
for b in blocks:
    text = b.get('text', '').strip()
    if len(text) > 30 and text[-1] not in '.!?:;,"\')-]':
        mid_sentence_ends += 1

mid_pct = mid_sentence_ends / max(len(blocks), 1) * 100
if mid_pct > 30:
    issues.append((
        "Continuity",
        f"{mid_sentence_ends} blocks ({mid_pct:.1f}%) end mid-sentence (may indicate hyphen-join failures or blob-split artefacts)",
        "Medium",
        "Review content_corrector hyphen-join pass; check blocks recovered via fitz dict for span-splitting"
    ))
else:
    print(f"[3] Continuity: ✅ PASS ({mid_pct:.1f}% mid-sentence ends)")

# ─── 4. FORMATTING CONSISTENCY ───────────────────────────────────────────────
type_counts = collections.Counter(b.get('type') for b in blocks)
unknown_types = {t: c for t, c in type_counts.items() if t not in
    ('paragraph','heading','list_item','caption','footer','header',
     'footnote','blank_page','toc','pyq_question','table_cell')}
if unknown_types:
    issues.append((
        "Formatting Consistency",
        f"Unknown block types present: {unknown_types}",
        "Low",
        "Normalise block types in the schema"
    ))
else:
    print(f"[4] Formatting Consistency: ✅ PASS | Types: {dict(type_counts.most_common(6))}")

# ─── 5. OCR / EXTRACTION ERRORS ──────────────────────────────────────────────
GARBAGE_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x80-\x9f\ufffd]')
garbled_blocks = [b for b in blocks if GARBAGE_CHARS.search(b.get('text',''))]
encoding_flagged = [b for b in blocks if b.get('encoding_error')]
corrupt_pct = len(garbled_blocks) / max(len(blocks), 1) * 100

if corrupt_pct > 5:
    issues.append((
        "OCR / Extraction Errors",
        f"{len(garbled_blocks)} blocks ({corrupt_pct:.1f}%) contain garbage/control characters",
        "High",
        "Apply _flag_mojibake_blocks filter and strip control chars from recovered fitz dict blocks"
    ))
elif garbled_blocks:
    issues.append((
        "OCR / Extraction Errors",
        f"{len(garbled_blocks)} blocks ({corrupt_pct:.1f}%) have minor encoding artefacts; {len(encoding_flagged)} explicitly flagged",
        "Low",
        "Strip control chars in content_corrector pass"
    ))
else:
    print(f"[5] OCR/Extraction Errors: ✅ PASS | Encoding-flagged: {len(encoding_flagged)}")

# ─── 6. DUPLICATE CONTENT ────────────────────────────────────────────────────
seen_texts = collections.Counter()
for b in blocks:
    t = re.sub(r'\s+', ' ', b.get('text','').strip().lower())[:120]
    if len(t) > 20:
        seen_texts[t] += 1

exact_dups = {t: c for t, c in seen_texts.items() if c > 2}
near_dups  = {t: c for t, c in seen_texts.items() if c == 2}

if exact_dups:
    issues.append((
        "Duplicate Content",
        f"{len(exact_dups)} text snippets appear >2 times (likely boilerplate running headers); {len(near_dups)} appear exactly twice",
        "Medium",
        "Tag repeated header/footer strings as is_boilerplate=True; deduplicate in _deduplicate_blocks"
    ))
    sample = list(exact_dups.items())[:3]
    for t, c in sample:
        print(f"    Dup ({c}x): {t[:60]!r}")
else:
    print(f"[6] Duplicate Content: ✅ PASS | Near-dups: {len(near_dups)}")

# ─── 7. DATA INTEGRITY ───────────────────────────────────────────────────────
missing_bbox   = sum(1 for b in blocks if not b.get('bbox'))
missing_pagnum = sum(1 for b in blocks if not b.get('page_num'))
missing_text   = sum(1 for b in blocks if not b.get('text','').strip())
pyq_count      = sum(1 for b in blocks if b.get('type') == 'pyq_question')

integrity_issues = []
if missing_bbox > 10:
    integrity_issues.append(f"{missing_bbox} blocks missing bbox")
if missing_pagnum > 0:
    integrity_issues.append(f"{missing_pagnum} blocks missing page_num")
if missing_text > 5:
    integrity_issues.append(f"{missing_text} blocks have empty text")

if integrity_issues:
    issues.append((
        "Data Integrity",
        "; ".join(integrity_issues),
        "Medium",
        "Add mandatory field validation gate in json_builder.py"
    ))
else:
    print(f"[7] Data Integrity: ✅ PASS | PYQ blocks preserved: {pyq_count}")

# ─── 8. READABILITY ──────────────────────────────────────────────────────────
very_short = [b for b in blocks if 0 < len(b.get('text','').strip()) < 5
              and not b.get('is_boilerplate')]
very_long  = [b for b in blocks if len(b.get('text','').strip()) > 2000
              and not b.get('is_boilerplate') and b.get('type') == 'paragraph']

read_issues = []
if len(very_short) > 50:
    read_issues.append(f"{len(very_short)} single-word/char blocks (span-split artefacts)")
if very_long:
    read_issues.append(f"{len(very_long)} paragraph blocks >2000 chars (may still be partial blobs)")

if read_issues:
    issues.append((
        "Readability",
        "; ".join(read_issues),
        "Medium" if very_long else "Low",
        "Merge short adjacent spans in content_corrector; flag long paragraphs for human review"
    ))
else:
    print(f"[8] Readability: ✅ PASS | Short blocks: {len(very_short)}, Very long paras: {len(very_long)}")

# ─── FINAL REPORT ────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  EXTRACTION QUALITY REVIEW — ONLY IAS: Art & Culture")
print("="*65)

severity_weights = {'High': 3, 'Medium': 2, 'Low': 1}
total_weight = sum(severity_weights[i[2]] for i in issues)
max_possible  = len([1,2,3,4,5,6,7,8]) * 3  # 8 checks × max weight 3

confidence = max(0, 100 - (total_weight / max_possible * 100))

high_issues   = [i for i in issues if i[2] == 'High']
medium_issues = [i for i in issues if i[2] == 'Medium']
low_issues    = [i for i in issues if i[2] == 'Low']

if confidence >= 85:
    quality = "Excellent"
elif confidence >= 70:
    quality = "Good"
elif confidence >= 50:
    quality = "Fair"
else:
    quality = "Poor"

print(f"\nOverall Extraction Quality: {quality}")
print(f"\nTotal text_blocks : {len(blocks):,}")
print(f"Total tables      : {len(tables)}")
print(f"Pages covered     : {total_pages}/270")
print(f"PYQ blocks rescued: {pyq_count}")

if issues:
    print(f"\nIssues Found ({len(issues)}):")
    for i, (itype, desc, sev, fix) in enumerate(issues, 1):
        print(f"\n  {i}. Issue Type  : {itype}")
        print(f"     Description : {desc}")
        print(f"     Severity    : {sev}")
        print(f"     Suggested Fix: {fix}")
else:
    print("\nIssues Found: None")

print(f"""
Summary:
  Total Issues Found  : {len(issues)}
  High Severity       : {len(high_issues)}
  Medium Severity     : {len(medium_issues)}
  Low Severity        : {len(low_issues)}
  Ready for AI Processing? : {'Yes' if len(high_issues) == 0 else 'No — resolve High issues first'}
  Confidence Score    : {confidence:.1f}%
""")
