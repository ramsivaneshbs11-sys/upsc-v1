import json, sys, os
sys.path.insert(0, '.')
from pathlib import Path
from PIL import Image
import numpy as np
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

json_path = 'outputs/Indian Art and Culture - Nitin Singhania 2nd(1)_extracted.json'
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

blocks = data.get('text_blocks', [])
p59_blocks = [b for b in blocks if b.get('page_num') == 59]
page_img_path = Path('outputs/page_images/page_059.png')

doc = fitz.open('inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf')
page = doc[58]
w_pts, h_pts = page.rect.width, page.rect.height

img = Image.open(page_img_path).convert('RGB')
img_w, img_h = img.size
sx = img_w / w_pts
sy = img_h / h_pts

from extraction.callout_detector import classify_highlight_color

print("Testing corrected bbox coordinate logic on Page 59:")
for b in p59_blocks[:10]:
    bbox = b.get('bbox')
    if bbox:
        x0_pt, x1_pt = min(bbox[0], bbox[2]), max(bbox[0], bbox[2])
        y_min_pt, y_max_pt = min(bbox[1], bbox[3]), max(bbox[1], bbox[3])
        
        px_x0 = int(x0_pt * sx)
        px_y0 = max(0, int(img_h - y_max_pt * sy))
        px_y1 = min(img_h, int(img_h - y_min_pt * sy))
        
        # sample strip inside left margin of box (e.g. px_x0 - 15 to px_x0 - 2)
        strip_x0 = max(0, px_x0 - 15)
        strip_x1 = max(0, px_x0 - 2)
        if strip_x1 <= strip_x0:
            strip_x0 = px_x0
            strip_x1 = px_x0 + 10
            
        strip = img.crop((strip_x0, px_y0, strip_x1, px_y1))
        arr = np.array(strip).reshape(-1, 3)
        if len(arr) > 0:
            median_rgb = tuple(np.median(arr, axis=0).astype(int))
            hl = classify_highlight_color(median_rgb)
        else:
            median_rgb = None
            hl = None
            
        text = b.get('text', '')[:45].encode('ascii', errors='replace').decode('ascii')
        print(f"y_range=[{y_min_pt:.1f}, {y_max_pt:.1f}] -> px_y=[{px_y0}, {px_y1}] | RGB={median_rgb} -> HL={hl} | {text!r}")
