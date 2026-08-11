import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json', encoding='utf-8') as f:
    art = json.load(f)

pimgs = art.get('page_images', [])
renders = [p for p in pimgs if p.get('type') == 'page_render']
print(f'page_images total: {len(pimgs)}, page_renders: {len(renders)}')

if renders:
    sample = renders[0]
    print(f'Sample entry: {sample}')
    # path is stored as "outputs/xxx/page_images/page_001.png"
    # _build_page_image_index resolves: output_dir.parent / rel_path
    # where output_dir is the JSON's sibling dir
    p = Path(sample.get('path', ''))
    print(f'Direct path exists: {p.exists()}  ({p})')
    # Try relative to CWD
    p2 = Path('.') / sample.get('path', '')
    print(f'Relative to CWD: {p2.resolve().exists()}  ({p2.resolve()})')

# Check what page_images dir actually exists
art_output_dir = Path('outputs/Art-and-Culture-Print-Friendly-Sample_extracted.json').parent
print(f'\noutput dir: {art_output_dir}')
pi_dir = art_output_dir / 'page_images'
print(f'page_images dir exists: {pi_dir.exists()}')
if pi_dir.exists():
    pngs = list(pi_dir.glob('*.png'))
    print(f'PNG files in it: {len(pngs)}')

# Check the actual output dirs
print('\nOutput dirs:')
for d in sorted(Path('outputs').iterdir()):
    if d.is_dir() and 'Art' in d.name:
        pi = d / 'page_images'
        print(f'  {d.name}: page_images_dir={pi.exists()}')
        if pi.exists():
            print(f'    PNGs: {len(list(pi.glob("*.png")))}')
