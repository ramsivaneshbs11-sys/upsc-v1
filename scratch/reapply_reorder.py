"""
Re-apply the column reorder pass directly to existing JSONs
(pages that weren't reordered at extraction time).
Uses fitz to get page widths, then calls reorder_all_pages.
"""
import json, sys, fitz, collections
from pathlib import Path
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from extraction.reorder_blocks import reorder_all_pages

def apply_reorder(json_path, pdf_path, label):
    p = Path(json_path)
    print(f"\n=== {label} ===")

    with open(p, encoding='utf-8') as f:
        data = json.load(f)

    blocks = data.get('text_blocks', [])

    # Get page widths from PDF
    doc = fitz.open(pdf_path)
    page_widths = {i + 1: doc[i].rect.width for i in range(len(doc))}
    doc.close()

    # Apply reorder
    reordered = reorder_all_pages(blocks, page_widths)

    # Count column switches before and after
    def count_switches(blks):
        page_map = collections.defaultdict(list)
        for b in blks:
            pg = b.get('page_num')
            if pg:
                page_map[pg].append(b)
        bad_pages = []
        for pg, pbs in sorted(page_map.items()):
            seq = []
            for b in pbs:
                bbox = b.get('bbox')
                if bbox:
                    seq.append('L' if bbox[0] < 297 else 'R')
            if 'L' in seq and 'R' in seq:
                sw = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i-1])
                if sw > 2:  # allow 1 L→R + 1 R→? = 2 transitions max on legit 2-col pages
                    bad_pages.append((pg, sw))
        return bad_pages

    bad_before = count_switches(blocks)
    bad_after  = count_switches(reordered)

    print(f"  Bad pages (>2 switches): {len(bad_before)} → {len(bad_after)}")
    if bad_after:
        for pg, sw in bad_after[:5]:
            print(f"    Page {pg}: {sw} switches")

    # Save
    # Re-index block IDs
    for idx, b in enumerate(reordered, start=1):
        b['block_id'] = f'blk_{idx:04d}'

    data['text_blocks'] = reordered
    data['block_count'] = len(reordered)

    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {p.name}")

apply_reorder(
    'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json',
    'inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf',
    'Nitin Singhania'
)

apply_reorder(
    'outputs/ONLY IAS - ART & CULTURE_extracted.json',
    'inputs/ONLY IAS - ART & CULTURE.pdf',
    'ONLY IAS'
)

print("\nDone.")
