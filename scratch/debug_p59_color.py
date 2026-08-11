import json, sys, os
sys.path.insert(0, '.')
from pathlib import Path
from PIL import Image
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = 'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])
p59_blocks = [b for b in blocks if b.get('page_num') == 59]

page_img_path = Path('outputs/page_images/page_059.png')
print(f"Page 59 image exists: {page_img_path.exists()}")

if page_img_path.exists():
    img = Image.open(page_img_path).convert('RGB')
    print(f"Image size: {img.size}")
    
    # Check sample block bboxes and RGB values
    import fitz
    doc = fitz.open('inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf')
    page = doc[58] # page index 58 is page_num 59
    w_pts, h_pts = page.rect.width, page.rect.height
    print(f"PDF page pts: {w_pts} x {h_pts}")
    
    from extraction.callout_detector import get_box_background_color, classify_highlight_color
    
    for b in p59_blocks[:10]:
        bbox = b.get('bbox')
        if bbox:
            sx = 612 / w_pts
            sy = 792 / h_pts
            x0_pt, y0_pt, x1_pt, y1_pt = bbox
            px_x0 = int(x0_pt * sx)
            px_y0 = int(792 - y1_pt * sy)
            px_y1 = int(792 - y0_pt * sy)
            print(f"bbox={bbox} -> px_x0={px_x0}, px_y0={px_y0}, px_y1={px_y1}")
            rgb = get_box_background_color(page_img_path, bbox, w_pts, h_pts)
            hl = classify_highlight_color(rgb)
            text = b.get('text', '')[:40].encode('ascii', errors='replace').decode('ascii')
            hl_str = str(hl)
            print(f"  RGB={rgb} -> HL={hl_str:15s} | text={text!r}")
