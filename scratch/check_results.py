import json
from pathlib import Path
p = Path('outputs/[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org_extracted.json')
if p.exists():
    with open(p, encoding='utf-8') as f:
        data = json.load(f)
    blocks = data.get('text_blocks', [])
    success = [b for b in blocks if b.get('source') == 'gemini_flash']
    failed = [b for b in blocks if b.get('source') == 'gemini_flash_failed']
    print('JSON File exists: YES')
    print(f'Total blocks: {len(blocks)}')
    print(f'Successful blocks: {len(success)}')
    print(f'Failed blocks: {len(failed)}')
    if failed:
        failed_pgs = sorted(list(set(b['page_num'] for b in failed)))
        print(f'Failed page numbers: {failed_pgs}')
else:
    print('JSON File exists: NO')
