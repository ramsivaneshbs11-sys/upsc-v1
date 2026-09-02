import argparse
import sys
import os
import logging
from pathlib import Path

# Fix HuggingFace symlink issue on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# Add root directory to sys.path so all packages resolve correctly
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from extraction.main import process_single_pdf
from preprocessing.main import process_single_json
from extraction.config import DEFAULT_OUTPUT_DIR as DEFAULT_EXTRACT_OUT
from preprocessing.config import DEFAULT_OUTPUT_DIR as DEFAULT_PREPROCESS_OUT

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("run_pipeline")

DIVIDER = "=" * 60


def run_pipeline(
    pdf_folder: Path,
    extract_out_dir: Path,
    preprocess_out_dir: Path,
    chunk_size: int,
    chunk_overlap: int
):
    """
    Full end-to-end pipeline:
        PDF Folder  →  Extraction (Docling JSON)  →  Preprocessing (Chunks)

    Args:
        pdf_folder:        Directory that contains the PDF input files.
        extract_out_dir:   Root output dir for extracted JSON + images.
        preprocess_out_dir: Output dir for preprocessed chunk JSON files.
        chunk_size:        Max characters per text chunk.
        chunk_overlap:     Overlap between consecutive text chunks.
    """
    # ── 1. Scan for PDFs (recursive — includes all subfolders) ───────────────
    pdf_files = sorted(pdf_folder.rglob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDF files found in: {pdf_folder}")
        sys.exit(1)

    print(f"\n{DIVIDER}")
    print(f"  PDF Folder  : {pdf_folder}")
    print(f"  PDFs found  : {len(pdf_files)}")
    print(f"  Extractions : {extract_out_dir}")
    print(f"  Chunks out  : {preprocess_out_dir}")
    print(f"{DIVIDER}\n")

    extract_success = []
    extract_failed  = []
    chunk_success   = []
    chunk_failed    = []

    # -- 2. Process each PDF ---------------------------------------------------
    for idx, pdf_file in enumerate(pdf_files, start=1):
        print(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_file.name}")
        print(f"  {'-'*50}")

        # -- Stage A: Extraction ----------------------------------------------
        print(f"  STAGE 1 - Extraction")
        clean_stem = pdf_file.stem.strip()
        file_extract_dir = extract_out_dir / clean_stem   # outputs/<pdf_stem>/
        ok = process_single_pdf(pdf_file, file_extract_dir)

        if not ok:
            logger.error(f"  [FAIL] Extraction failed for: {pdf_file.name} - skipping preprocessing.")
            extract_failed.append(pdf_file.name)
            continue

        extract_success.append(pdf_file.name)
        json_path = file_extract_dir / f"{clean_stem}_extracted.json"
        print(f"  [OK] Extracted -> {json_path}")

        # -- Stage B: Preprocessing / Chunking --------------------------------
        print(f"\n  STAGE 2 - Preprocessing & Chunking")
        ok = process_single_json(
            json_path=json_path,
            output_dir=preprocess_out_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        if ok:
            chunk_success.append(pdf_file.name)
        else:
            logger.error(f"  [FAIL] Preprocessing failed for: {pdf_file.name}")
            chunk_failed.append(pdf_file.name)

    # -- 3. Final summary ------------------------------------------------------
    print(f"\n{DIVIDER}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Extraction   - {len(extract_success)} succeeded, {len(extract_failed)} failed")
    print(f"  Preprocessing- {len(chunk_success)} succeeded, {len(chunk_failed)} failed")

    if extract_failed:
        print(f"\n  Extraction failures:")
        for name in extract_failed:
            print(f"    [FAIL] {name}")

    if chunk_failed:
        print(f"\n  Preprocessing failures:")
        for name in chunk_failed:
            print(f"    [FAIL] {name}")

    print(f"\n  Extracted JSONs  ->  {extract_out_dir}")
    print(f"  Preprocessed     ->  {preprocess_out_dir}")
    print(f"{DIVIDER}\n")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "End-to-End Pipeline:\n"
            "  1. Extracts text/tables/images from all PDFs in a folder (via Docling)\n"
            "  2. Preprocesses each extracted JSON into semantic chunks (layout-aware)\n\n"
            "Usage:\n"
            "  python run_pipeline.py \"C:\\path\\to\\pdf_folder\"\n"
            "  python run_pipeline.py \"C:\\path\\to\\pdf_folder\" --chunk-size 1500 --chunk-overlap 300"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "pdf_folder",
        type=str,
        help="Path to a folder containing one or more PDF files."
    )
    parser.add_argument(
        "--extract-output-dir",
        type=str,
        default=str(DEFAULT_EXTRACT_OUT),
        help=f"Directory to store extracted JSON and images. (default: {DEFAULT_EXTRACT_OUT})"
    )
    parser.add_argument(
        "--preprocess-output-dir",
        type=str,
        default=str(DEFAULT_PREPROCESS_OUT),
        help=f"Directory to store preprocessed chunks. (default: {DEFAULT_PREPROCESS_OUT})"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Max characters per text chunk. (default: 1000)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Overlap characters between consecutive chunks. (default: 200)"
    )

    args = parser.parse_args()

    pdf_folder = Path(args.pdf_folder)
    if not pdf_folder.is_dir():
        logger.error(f"The provided path is not a directory: {pdf_folder}")
        sys.exit(1)

    run_pipeline(
        pdf_folder=pdf_folder,
        extract_out_dir=Path(args.extract_output_dir),
        preprocess_out_dir=Path(args.preprocess_output_dir),
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )


if __name__ == "__main__":
    main()
