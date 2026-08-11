import json
with open('outputs/[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org_extracted.json', encoding='utf-8') as f:
    data = json.load(f)
blocks = [b for b in data.get('text_blocks', []) if b.get('page_num') in [54, 79]]
for b in blocks:
    print(f"Page {b['page_num']} ({b['source']}): {b['text'][:150]}...")
