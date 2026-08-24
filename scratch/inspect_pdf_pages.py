import fitz  # PyMuPDF
from pathlib import Path

pdf_path = Path(r"c:\Users\vishn\Downloads\RAG-main\BOOKS\TRIBES INDIA.pdf")

if not pdf_path.exists():
    # Try alternate location
    pdf_path = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\uploads\anthropology\51682a62-60f6-49f0-8862-bbf6925d885c.pdf")

print(f"Inspecting PDF: {pdf_path}")
if not pdf_path.exists():
    print("PDF not found at either location!")
    sys.exit(1)

doc = fitz.open(str(pdf_path))
print(f"Total pages: {len(doc)}")

target_pages = [12, 13, 14, 15, 16, 17, 18, 191, 196, 198, 199, 200, 205]

for p in target_pages:
    if p > len(doc):
        print(f"Page {p} is out of range.")
        continue
    page = doc[p - 1]
    text = page.get_text().strip()
    rects = page.get_drawings()
    images = page.get_images()
    
    print(f"\n--- Page {p} ---")
    print(f"Raw PyMuPDF Text length: {len(text)}")
    print(f"Number of local images: {len(images)}")
    print(f"Number of drawings (shapes): {len(rects)}")
    if text:
        print(f"Sample Text: {text[:150]}...")
    else:
        print("No raw text in PDF (suggests scanned/image page).")

doc.close()
