"""
run_scanned_ingestion.py
────────────────────────
Batch processor for scanned PDFs using Gemini Vision + standard ingestion pipeline.

Steps for each PDF in the input folder:
  1. Extract using gemini_batch_extract.py -> generates output/<pdf_stem>_extracted.json
  1.5 Auto recheck: scan for blank/failed pages -> re-extract them (up to 3 rounds)
  2. Ingest using ide_gemini_ingest.py -> preprocessing, chunking, embedding, Qdrant/PostgreSQL ingestion

Usage:
  python run_scanned_ingestion.py "C:/path/to/scanned_pdfs_folder" --classification Anthropology
  python run_scanned_ingestion.py "C:/path/to/scanned_pdfs_folder" --classification History
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add root folder to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

def run_scanned_folder(pdf_path_or_folder: Path, classification: str, delay: float):
    if pdf_path_or_folder.is_file():
        if pdf_path_or_folder.suffix.lower() == ".pdf":
            pdf_files = [pdf_path_or_folder]
        else:
            print(f"\n❌ Provided file is not a PDF: {pdf_path_or_folder}")
            return
    else:
        pdf_files = sorted(list(pdf_path_or_folder.rglob("*.pdf")))
    
    if not pdf_files:
        print(f"\n❌ No PDF files found in: {pdf_path_or_folder}")
        return

    print("=" * 70)
    print(f"  SCANNED BATCH INGESTION PIPELINE")
    print(f"  Input Path    : {pdf_path_or_folder}")
    print(f"  PDFs Found    : {len(pdf_files)}")
    print(f"  Classification: {classification}")
    print("=" * 70)

    for idx, pdf_path in enumerate(pdf_files, start=1):
        print(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print("-" * 50)
        
        # 1. Run Gemini extraction
        print(f"👉 STAGE 1: Running Gemini Vision Extraction...")
        extract_cmd = [
            sys.executable,
            "gemini_batch_extract.py",
            str(pdf_path),
            "--delay", str(delay)
        ]
        
        # Run subprocess and stream output to console
        res = subprocess.run(extract_cmd, cwd=str(ROOT_DIR))
        if res.returncode != 0:
            print(f"❌ Gemini extraction failed for {pdf_path.name}. Skipping to next PDF.")
            continue

        # ── STAGE 1.5: Auto blank-page recheck & re-extract ─────────────────
        print(f"\n🔍 STAGE 1.5: Scanning for blank/failed pages and re-extracting...")
        _auto_recheck_and_reextract(pdf_path, delay)
        # ─────────────────────────────────────────────────────────────────────
            
        # The expected output JSON path from gemini_batch_extract.py
        # It consolidated JSON at output/<pdf_stem>_extracted.json
        extracted_json = ROOT_DIR / "output" / f"{pdf_path.stem.strip()}_extracted.json"
        
        if not extracted_json.exists():
            print(f"❌ Consolidated JSON not found: {extracted_json}. Skipping.")
            continue
            
        print(f"✅ Gemini extraction succeeded -> {extracted_json.name}")
        
        # 2. Run Database & Qdrant Ingestion
        print(f"👉 STAGE 2: Preprocessing, Embedding & Upserting to Database...")
        ingest_cmd = [
            sys.executable,
            "ide_gemini_ingest.py",
            str(extracted_json),
            "--pdf", str(pdf_path),
            "--classification", classification
        ]
        
        res_ingest = subprocess.run(ingest_cmd, cwd=str(ROOT_DIR))
        if res_ingest.returncode != 0:
            print(f"❌ Ingestion pipeline failed for {pdf_path.name}.")
        else:
            print(f"🎉 Fully Ingested successfully: {pdf_path.name}")

    print("\n" + "=" * 70)
    print("  BATCH PIPELINE RUN COMPLETE")
    print("=" * 70)


def _auto_recheck_and_reextract(pdf_path: Path, delay: float, max_rounds: int = 3):
    """
    After initial extraction, scan the output folder for pages that are blank
    (is_blank=True with no actual text) or have an extraction_error, then
    remove them from progress.json and re-run gemini_batch_extract.py so
    those specific pages get a fresh attempt.

    Repeats up to `max_rounds` times in case re-extraction itself produces
    new blank pages (e.g. due to temporary 503 errors).
    """
    import json

    pdf_stem = pdf_path.stem.strip()
    output_dir = ROOT_DIR / "output" / pdf_stem
    progress_file = output_dir / "progress.json"

    if not output_dir.exists() or not progress_file.exists():
        print("  ⚠️  No output folder or progress.json found – skipping recheck.")
        return

    for round_num in range(1, max_rounds + 1):
        # ── Find blank / errored pages ───────────────────────────────────────
        blank_pages = []
        for page_json in sorted(output_dir.glob("page_*.json")):
            try:
                data = json.loads(page_json.read_text(encoding="utf-8"))
            except Exception:
                continue

            has_text = bool(data.get("text_blocks") or data.get("tables"))
            has_error = bool(data.get("extraction_error"))
            is_marked_blank = data.get("is_blank", False)

            # Flag pages that are empty AND either explicitly blank or errored
            if not has_text and (is_marked_blank or has_error):
                blank_pages.append(data.get("page_num") or int(page_json.stem.split("_")[1]))

        if not blank_pages:
            print(f"  ✅ Round {round_num}: No blank/failed pages found. Moving on.")
            break

        print(f"  ⚠️  Round {round_num}: Found {len(blank_pages)} blank/failed pages: {blank_pages}")
        print(f"      Resetting and re-extracting these pages...")

        # ── Reset: remove from progress.json & delete page JSONs ────────────
        try:
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
            extracted = progress.get("extracted_pages", [])
            progress["extracted_pages"] = [p for p in extracted if p not in blank_pages]
            progress_file.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"  ❌ Could not update progress.json: {e}")
            break

        for p in blank_pages:
            page_file = output_dir / f"page_{p:04d}.json"
            if page_file.exists():
                page_file.unlink()

        # ── Re-run extraction (only missing pages will be processed) ─────────
        extract_cmd = [
            sys.executable,
            "gemini_batch_extract.py",
            str(pdf_path),
            "--delay", str(delay),
        ]
        res = subprocess.run(extract_cmd, cwd=str(ROOT_DIR))
        if res.returncode != 0:
            print(f"  ❌ Re-extraction subprocess failed (round {round_num}).")
            break

        print(f"  ✅ Round {round_num} re-extraction complete.")
    else:
        print(f"  ⚠️  Reached max re-check rounds ({max_rounds}). Some pages may still be blank.")


def main():
    parser = argparse.ArgumentParser(
        description="Run end-to-end Gemini extraction & ingestion for a folder of scanned PDFs."
    )
    parser.add_argument(
        "pdf_folder",
        type=str,
        help="Path to folder containing scanned PDFs."
    )
    parser.add_argument(
        "--classification",
        type=str,
        required=True,
        choices=["History", "Anthropology"],
        help="Document classification: 'History' or 'Anthropology'"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between page API requests (default 2.0)."
    )
    
    args = parser.parse_args()
    pdf_path_or_folder = Path(args.pdf_folder)
    
    if not pdf_path_or_folder.exists():
        print(f"❌ Error: Path does not exist: {pdf_path_or_folder}")
        sys.exit(1)
        
    run_scanned_folder(pdf_path_or_folder, args.classification, args.delay)

if __name__ == "__main__":
    main()
