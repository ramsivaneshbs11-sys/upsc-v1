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
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("test_prompt_extract")

from extraction.gemini_page_extractor import extract_document_with_gemini

def main():
    pdf_path   = Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\uploads\anthropology\1507114722Quadrant1.pdf")
    output_dir = ROOT_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"Testing optimized prompts on page 2 of {pdf_path.name}")
    logger.info("=" * 60)

    # Extract page 2 (contains a table and a TOC contents list)
    _, final_json = extract_document_with_gemini(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages_list=[2]
    )

    # Print extraction summary
    summary = final_json.get("extraction_summary", {})
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total Text Blocks: {summary.get('total_text_blocks')}")
    print(f"Total Tables     : {summary.get('total_tables')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
