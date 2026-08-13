import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from extraction.text_service import extract_text
from extraction.table_service import extract_tables
from extraction.gemini_page_extractor import _merge_page

def main():
    pdf_path = ROOT_DIR / "[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf"
    page_num = 54  # Biography of Raja Rammohan Roy
    
    print(f"Running Gemini 3.5 Flash extraction on page {page_num}...")
    
    # 1. Run text extraction
    text_blocks = extract_text(pdf_path, page_num)
    
    # 2. Run table extraction
    tables = extract_tables(pdf_path, page_num)
    
    # 3. Merge page results
    page_json = _merge_page(page_num, text_blocks, tables)
    
    # Print pretty JSON
    print("\n--- EXTRACTED JSON OUTPUT ---")
    print(json.dumps(page_json, indent=2, ensure_ascii=False))
    print("-----------------------------\n")

if __name__ == "__main__":
    main()
