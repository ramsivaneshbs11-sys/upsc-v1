import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("test_table_extract")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from extraction.table_service import extract_tables

def main():
    pdf_path = ROOT_DIR / "uploads" / "anthropology" / "01bded9f-4da3-427c-9111-3acd4a37f858.pdf"
    logger.info(f"Testing table extraction on page 18 of: {pdf_path}")
    tables = extract_tables(pdf_path, 18)
    logger.info(f"Extracted {len(tables)} tables")
    print("\n--- EXTRACTED TABLES ---")
    import json
    print(json.dumps(tables, indent=2))
    print("------------------------\n")

if __name__ == "__main__":
    main()
