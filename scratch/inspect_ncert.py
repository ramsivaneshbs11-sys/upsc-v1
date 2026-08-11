"""
Inspect [NCERT] The Story of Civilization Part I (Arjun Dev) PDF.
Checks page count, text availability, scanned vs digital ratio, and layout.
"""
import fitz, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

pdf_path = Path(r"c:\Users\vishn\Downloads\upsc-pdf-extraction-pipeline-main\upsc-pdf-extraction-pipeline-main\[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf")

if not pdf_path.exists():
    print(f"File NOT found at {pdf_path}")
    sys.exit(1)

doc = fitz.open(str(pdf_path))
total_pages = len(doc)
print(f"PDF Loaded Successfully: {pdf_path.name}")
print(f"Total Pages: {total_pages}")
print(f"File Size: {pdf_path.stat().st_size / (1024*1024):.2f} MB\n")

# Check sample pages (e.g. page 1, 5, 10, 20, 50)
sample_pages = [1, 5, 10, 20, 50]
sample_pages = [p for p in sample_pages if p <= total_pages]

total_text_len = 0
scanned_page_count = 0

print("=== SAMPLE PAGE AUDIT ===")
for pno in sample_pages:
    page = doc[pno - 1]
    text = page.get_text()
    images = page.get_images()
    tlen = len(text.strip())
    total_text_len += tlen
    is_scanned = tlen < 50
    if is_scanned:
        scanned_page_count += 1
    
    print(f"Page {pno:3d} | Text Length: {tlen:5d} chars | Embedded Images: {len(images):2d} | Type: {'[SCANNED IMAGE]' if is_scanned else '[DIGITAL TEXT]'}")
    if tlen > 0:
        preview = text.strip()[:100].replace('\n', ' ')
        print(f"         Preview: {preview!r}")

print(f"\n=== OVERALL PDF ASSESSMENT ===")
if scanned_page_count == len(sample_pages):
    print("Assessment: Fully SCANNED PDF (No native text layer found).")
elif scanned_page_count > 0:
    print("Assessment: HYBRID / MIXED PDF (Some pages scanned, some digital).")
else:
    print("Assessment: BORN-DIGITAL PDF (Clean text layer available across all sample pages).")

doc.close()
