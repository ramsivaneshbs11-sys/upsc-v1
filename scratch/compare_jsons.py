import json
from pathlib import Path

# Load files
docling_path = Path('scratch/test_docling_out/145793840413ET_docling.json')
gemini_path = Path('scratch/test_gemini_out/145793840413ET_gemini.json')

with open(docling_path, 'r', encoding='utf-8') as f:
    d_data = json.load(f)
with open(gemini_path, 'r', encoding='utf-8') as f:
    g_data = json.load(f)

print('=== COMPARISON REPORT ===')

# Page count
print(f'Docling total pages: 12')
print(f'Gemini total pages: {g_data.get("total_pages")}')

# Text block structures
d_blocks = d_data.get('text_blocks', [])
g_blocks = []
for p in g_data.get('pages', []):
    g_blocks.extend(p.get('text_blocks', []))

print(f'\n--- Structural counts ---')
print(f'Docling non-boilerplate blocks: {len([b for b in d_blocks if not b.get("is_boilerplate")])}')
print(f'Gemini non-boilerplate blocks: {len(g_blocks)}')

# Tables
d_tables = d_data.get('tables', [])
g_tables = []
for p in g_data.get('pages', []):
    g_tables.extend(p.get('tables', []))

print(f'\n--- Tables ---')
print(f'Docling Tables extracted: {len(d_tables)}')
for t in d_tables:
    print(f'  - Docling Table on Page {t.get("page_num")}: rows={t.get("row_count")}, cols={t.get("column_count")}')

print(f'Gemini Tables extracted: {len(g_tables)}')
for t in g_tables:
    print(f'  - Gemini Table on Page {t.get("page_num")}: rows={t.get("row_count")}, cols={t.get("column_count")}')

# Compare Text Content Accuracy (Jaccard similarity of entire document body text)
d_text_corp = " ".join([b.get('text', '') for b in d_blocks if not b.get('is_boilerplate')]).lower()
g_text_corp = " ".join([b.get('text', '') for b in g_blocks]).lower()

import re
d_words = set(re.findall(r'\b[a-z]{3,}\b', d_text_corp))
g_words = set(re.findall(r'\b[a-z]{3,}\b', g_text_corp))

overlap = len(d_words & g_words)
union = len(d_words | g_words)
accuracy = (overlap / union) * 100 if union > 0 else 0.0

print(f'\n--- Vocabulary Accuracy & Similarity ---')
print(f'Docling unique words: {len(d_words)}')
print(f'Gemini unique words: {len(g_words)}')
print(f'Vocabulary Overlap: {overlap} matching words')
print(f'Vocabulary Jaccard Accuracy: {accuracy:.2f}%')
