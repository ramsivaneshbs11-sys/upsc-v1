import fitz
from pathlib import Path

pdf_path = Path(r"c:\Users\vishn\Downloads\RAG-main\BOOKS\TRIBES INDIA.pdf")
out_dir = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\scratch")

doc = fitz.open(str(pdf_path))

pages_to_render = [12, 205]

for p in pages_to_render:
    page = doc[p - 1]
    pix = page.get_pixmap(dpi=150)
    out_path = out_dir / f"inspect_page_{p}.jpg"
    pix.save(str(out_path))
    print(f"Saved: {out_path} (Size: {out_path.stat().st_size} bytes)")

doc.close()
