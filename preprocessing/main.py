"""
main.py
────────
Standalone CLI entry point for text preprocessing & chunking stage.
"""

import sys
import json
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocessing.text_cleaner import clean_extracted_json
from preprocessing.chunker import create_chunks
from preprocessing.config import DEFAULT_OUTPUT_DIR, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, DEFAULT_MIN_PAGE_SIZE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preprocessing_cli")


def process_single_json(
    json_path: Path,
    output_dir: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_page_size: int = DEFAULT_MIN_PAGE_SIZE,
) -> bool:
    """
    Runs text cleaning and chunking on a single extracted JSON file.
    """
    logger.info(f"Preprocessing JSON file: {json_path.name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Clean extracted JSON
    clean_data = clean_extracted_json(json_path)

    # 2. Generate chunks
    result = create_chunks(clean_data, max_chunk_size=chunk_size, min_page_size=min_page_size)

    # 3. Save preprocessed chunk JSON
    out_name = f"{json_path.stem.strip()}_preprocessed.json"
    out_path = output_dir / out_name

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved preprocessed chunks ({result['chunk_count']} chunks) -> {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="UPSC Preprocessor & Chunker")
    parser.add_argument("json_path", type=str, help="Path to extracted JSON file")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--chunk-size",    type=int, default=DEFAULT_CHUNK_SIZE,    help="Max chars per chunk (default 1200)")
    parser.add_argument("--min-page-size", type=int, default=DEFAULT_MIN_PAGE_SIZE, help="Min page size before merging (default 300)")
    parser.add_argument("--chunk-overlap",  type=int, default=0,                    help="Legacy flag — ignored in page-wise mode")

    args = parser.parse_args()
    json_path = Path(args.json_path)

    if not json_path.exists():
        logger.error(f"Input JSON does not exist: {json_path}")
        sys.exit(1)

    success = process_single_json(json_path, Path(args.output_dir), args.chunk_size, args.chunk_overlap, args.min_page_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
