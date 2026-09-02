"""
run_batch_inputs.py
────────────────────
Batch extraction pipeline runner for both P-01 and Semester-V input directories.

Runs extraction + preprocessing on all PDFs found under:
  - inputs/P-01/
  - inputs/Semester-V/  (recursive, includes all 3 subject sub-folders)

Usage:
    python run_batch_inputs.py
    python run_batch_inputs.py --chunk-size 1200 --chunk-overlap 200
"""

import sys
import os
import logging
import time
from pathlib import Path
from datetime import datetime

# Fix HuggingFace symlink issue on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from extraction.main import process_single_pdf
from preprocessing.main import process_single_json
from extraction.config import DEFAULT_OUTPUT_DIR as DEFAULT_EXTRACT_OUT
from preprocessing.config import DEFAULT_OUTPUT_DIR as DEFAULT_PREPROCESS_OUT

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("run_batch_inputs")

DIVIDER = "=" * 70


def process_folder(
    pdf_folder: Path,
    extract_out_dir: Path,
    preprocess_out_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    folder_label: str
) -> dict:
    """
    Processes all PDFs (recursive) inside pdf_folder.
    Returns a stats dict.
    """
    pdf_files = sorted(pdf_folder.rglob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in: {pdf_folder}")
        return {"total": 0, "extract_ok": 0, "extract_fail": [], "chunk_ok": 0, "chunk_fail": []}

    print(f"\n{DIVIDER}")
    print(f"  FOLDER  : {folder_label}")
    print(f"  PDFs    : {len(pdf_files)}")
    print(f"  Extract -> {extract_out_dir}")
    print(f"  Chunks  -> {preprocess_out_dir}")
    print(DIVIDER)

    stats = {
        "total": len(pdf_files),
        "extract_ok": 0,
        "extract_fail": [],
        "chunk_ok": 0,
        "chunk_fail": [],
    }

    for idx, pdf_file in enumerate(pdf_files, start=1):
        t0 = time.time()
        rel_path = pdf_file.relative_to(pdf_folder)
        print(f"\n  [{idx:>3}/{len(pdf_files)}] {rel_path}")
        print(f"           {'-' * 56}")

        # ── Stage 1: Extraction ───────────────────────────────────────────────
        clean_stem = pdf_file.stem.strip()
        file_extract_dir = extract_out_dir / clean_stem
        try:
            ok = process_single_pdf(pdf_file, file_extract_dir)
        except Exception as exc:
            logger.error(f"  [ERROR] Extraction crashed: {exc}")
            ok = False

        if not ok:
            logger.error(f"  [FAIL] Extraction: {pdf_file.name}")
            stats["extract_fail"].append(str(rel_path))
            continue

        stats["extract_ok"] += 1
        json_path = file_extract_dir / f"{clean_stem}_extracted.json"
        elapsed = time.time() - t0
        print(f"  [OK] Extracted -> {json_path.name}  ({elapsed:.1f}s)")

        # ── Stage 2: Preprocessing ────────────────────────────────────────────
        try:
            ok = process_single_json(
                json_path=json_path,
                output_dir=preprocess_out_dir,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
        except Exception as exc:
            logger.error(f"  [ERROR] Preprocessing crashed: {exc}")
            ok = False

        if ok:
            stats["chunk_ok"] += 1
            print(f"  [OK] Preprocessed -> chunks written")
        else:
            logger.error(f"  [FAIL] Preprocessing: {pdf_file.name}")
            stats["chunk_fail"].append(str(rel_path))

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch pipeline: extract + preprocess all P-01 and Semester-V PDFs"
    )
    parser.add_argument("--extract-output-dir", type=str, default=str(DEFAULT_EXTRACT_OUT))
    parser.add_argument("--preprocess-output-dir", type=str, default=str(DEFAULT_PREPROCESS_OUT))
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument(
        "--only",
        choices=["p01", "sem5", "all"],
        default="all",
        help="Which folder set to process: 'p01', 'sem5', or 'all' (default)"
    )
    args = parser.parse_args()

    extract_out  = Path(args.extract_output_dir)
    preprocess_out = Path(args.preprocess_output_dir)

    # ── Resolve input directories ─────────────────────────────────────────────
    p01_dir  = ROOT_DIR / "inputs" / "P-01"
    sem5_dir = ROOT_DIR / "inputs" / "Semester-V"

    run_p01  = args.only in ("p01", "all")
    run_sem5 = args.only in ("sem5", "all")

    all_stats = {}
    grand_start = time.time()

    # ── Run P-01 ─────────────────────────────────────────────────────────────
    if run_p01 and p01_dir.is_dir():
        all_stats["P-01"] = process_folder(
            pdf_folder=p01_dir,
            extract_out_dir=extract_out,
            preprocess_out_dir=preprocess_out,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            folder_label="P-01 (Legacy IGNOU modules)",
        )
    elif run_p01:
        logger.error(f"P-01 folder not found: {p01_dir}")

    # ── Run Semester-V ────────────────────────────────────────────────────────
    if run_sem5 and sem5_dir.is_dir():
        all_stats["Semester-V"] = process_folder(
            pdf_folder=sem5_dir,
            extract_out_dir=extract_out,
            preprocess_out_dir=preprocess_out,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            folder_label="Semester-V (BHIC-111 / BHIC-112 / BHIE-141)",
        )
    elif run_sem5:
        logger.error(f"Semester-V folder not found: {sem5_dir}")

    # ── Grand Summary ─────────────────────────────────────────────────────────
    total_elapsed = time.time() - grand_start
    print(f"\n{DIVIDER}")
    print(f"  BATCH PIPELINE COMPLETE  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total runtime : {total_elapsed/60:.1f} min")
    print(DIVIDER)

    total_pdfs = sum(s["total"] for s in all_stats.values())
    total_ok   = sum(s["extract_ok"] for s in all_stats.values())
    total_fail = sum(len(s["extract_fail"]) for s in all_stats.values())

    print(f"\n  {'Folder':<20} {'PDFs':>6} {'Extracted':>10} {'Failed':>8} {'Chunked':>9}")
    print(f"  {'-'*60}")
    for label, s in all_stats.items():
        print(
            f"  {label:<20} {s['total']:>6} "
            f"{s['extract_ok']:>10} {len(s['extract_fail']):>8} {s['chunk_ok']:>9}"
        )
    print(f"  {'-'*60}")
    print(f"  {'TOTAL':<20} {total_pdfs:>6} {total_ok:>10} {total_fail:>8}")

    if any(s["extract_fail"] for s in all_stats.values()):
        print(f"\n  Extraction failures:")
        for label, s in all_stats.items():
            for f in s["extract_fail"]:
                print(f"    [FAIL] [{label}] {f}")

    if any(s["chunk_fail"] for s in all_stats.values()):
        print(f"\n  Preprocessing failures:")
        for label, s in all_stats.items():
            for f in s["chunk_fail"]:
                print(f"    [FAIL] [{label}] {f}")

    print(f"\n  Extracted JSONs  ->  {extract_out}")
    print(f"  Preprocessed     ->  {preprocess_out}")
    print(f"{DIVIDER}\n")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
