import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT_DIR / "outputs" / "ncert_extraction_pages_9_13_14_15_16.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("specific_pages_extract")

from extraction.gemini_page_extractor import extract_document_with_gemini

def main():
    pdf_path   = ROOT_DIR / "[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf"
    output_dir = ROOT_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"Starting specific pages Gemini extraction: {pdf_path.name}")
    logger.info("=" * 60)

    # Call with pages_list=[9, 13, 14, 15, 16]
    _, final_json = extract_document_with_gemini(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages_list=[9, 13, 14, 15, 16]
    )

    # Print extraction summary
    summary = final_json.get("extraction_summary", {})
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Total pages      : {final_json.get('total_pages')}")
    print(f"  Pages w/ content : {summary.get('pages_with_content')}")
    print(f"  Blank pages      : {summary.get('blank_pages')} {summary.get('blank_page_numbers')}")
    print(f"  Total text blocks: {summary.get('total_text_blocks')}")
    print(f"  Total tables     : {summary.get('total_tables')}")
    print(f"  Elapsed          : {summary.get('elapsed_seconds')}s")
    print(f"  Engine           : {final_json.get('extraction_engine')}")
    print("=" * 60)
    
    # Generate the output name matching logic in extractor
    pages_to_extract = [9, 13, 14, 15, 16]
    pages_str = "_".join(map(str, pages_to_extract))
    expected_filename = f"{pdf_path.stem.strip()}_pages_{pages_str}_extracted.json"
    print(f"\nJSON saved to: {output_dir / expected_filename}")

if __name__ == "__main__":
    main()
