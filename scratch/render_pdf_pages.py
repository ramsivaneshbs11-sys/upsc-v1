"""
render_pdf_pages.py
────────────────────
Renders each page of a PDF to a PNG image for IDE vision extraction.
"""
import sys
import fitz
from pathlib import Path

def render_pages(pdf_path: str, output_dir: str, dpi: int = 150):
    doc = fitz.open(pdf_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    
    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        img_path = out / f"page_{i+1:04d}.png"
        pix.save(str(img_path))
        if (i + 1) % 10 == 0:
            print(f"  Rendered {i+1}/{doc.page_count} pages...")
    
    print(f"\nDone! {doc.page_count} pages rendered to: {out}")
    doc.close()

if __name__ == "__main__":
    render_pages(
        pdf_path="Brain tree VOL-1.pdf",
        output_dir="scratch/brain_tree_pages",
        dpi=150
    )
