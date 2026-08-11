import sys
sys.path.insert(0, '.')
from extraction.smart_router import route_extraction
from extraction.gemini_extractor import extract_with_gemini_flash, GEMINI_MODEL
print('smart_router    : OK')
print('gemini_extractor: OK')
print('Gemini model    :', GEMINI_MODEL)

from extraction.pdf_type_detector import is_scanned_pdf
from pathlib import Path

pdfs = [
    Path('inputs/ONLY IAS - ART & CULTURE.pdf'),
    Path('inputs/Indian Art and Culture - Nitin Singhania 2nd(1).pdf'),
    Path('[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf'),
]

print('\nRoute detection test:')
for p in pdfs:
    if p.exists():
        engine = 'GEMINI Flash' if is_scanned_pdf(p) else 'DOCLING (Local)'
        print(f'  {p.name[:55]:55s} -> {engine}')
    else:
        print(f'  [NOT FOUND] {p.name[:50]}')
