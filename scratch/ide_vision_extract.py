"""
ide_vision_extract.py
──────────────────────────────────────────────────────────────────────────────
Extracts all pages of a PDF using Gemini Flash Vision directly — no intermediate
image files saved to disk. Each page is rendered in-memory, sent to Gemini, and
the extracted text is accumulated into a structured JSON.

Features:
  - Renders each page in-memory using PyMuPDF (fitz) — no disk PNG files
  - Calls Gemini Flash Vision API directly (uses GEMINI_API_KEY from .env)
  - NOT using the FastAPI endpoint — purely a local script
  - Auto-saves progress every SAVE_EVERY pages (safe to interrupt and resume)
  - Skips blank pages automatically
  - Strips boilerplate (Telegram headers, watermarks, footer page numbers)
  - Outputs structured JSON matching the standard extraction schema

Usage:
    python scratch/ide_vision_extract.py
    python scratch/ide_vision_extract.py --pdf "Brain tree VOL-1.pdf" --output scratch/my_doc_extracted.json
    python scratch/ide_vision_extract.py --start-page 50   # resume from page 50

After completion, run:
    python ide_gemini_ingest.py scratch/my_doc_extracted.json --pdf "Brain tree VOL-1.pdf" --classification Anthropology
"""

import sys
import os
import re
import json
import time
import logging
import argparse
from pathlib import Path

# Workspace root setup
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from extraction.gemini_client import render_page_to_jpeg, call_gemini, get_gemini_client

import fitz  # PyMuPDF

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ide_vision_extract")

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_PDF    = ROOT_DIR / "Brain tree VOL-1.pdf"
DEFAULT_OUTPUT = ROOT_DIR / "scratch" / "my_doc_extracted.json"
SAVE_EVERY     = 10       # Save progress JSON every N pages
RETRY_DELAY    = 5        # Seconds to wait before retrying a failed page
MAX_RETRIES    = 3        # Max retries per page

DIVIDER = "=" * 65

# ── Boilerplate patterns to strip ──────────────────────────────────────────────
BOILERPLATE_PATTERNS = [
    r"Join Our Telegram Channel.*?For Instant Updates",
    r"www\.freeupscmaterials\.org",
    r"Anthropology Paper \d+ - Volume \d+",
    r"G\.S\.\s*Kartic\s*\(karticsg@gmail\.com\)",
    r"G\.S\.\s*Kartic\s*\[karticsg@gmail\.com\]",
    r"Social and Cultural Anthropology",
    r"^\s*\d+\s*$",   # Standalone page numbers
]
_BOILERPLATE_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in BOILERPLATE_PATTERNS]

# ── Extraction prompt ──────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are a precise OCR and document structure extractor.

Extract ALL text from this scanned PDF page into a structured JSON object.

RULES:
1. Extract every visible word and sentence accurately — no hallucination, no additions.
2. Identify the block type for each text unit:
   - "heading" for section/chapter titles (typically bold, larger font, numbered like 1.1, 2.3 etc.)
   - "subheading" for sub-section titles
   - "paragraph" for regular body text
   - "list_item" for bullet points or numbered list items
   - "table" for any table (extract as a list of row arrays)
   - "caption" for figure/diagram captions
3. SKIP completely: Telegram channel headers, watermarks (www.freeupscmaterials.org), page numbers alone, footer lines (G.S. Kartic email lines, "Anthropology Paper" footer).
4. If page is blank or has only watermarks/boilerplate, return: {"page_num": N, "text_blocks": [], "tables": [], "is_blank": true}
5. For tables: return {"type": "table", "rows": [["col1", "col2"], ["val1", "val2"]]}
6. Preserve bold markers for key terms by wrapping with ** like **term**

OUTPUT FORMAT (strict JSON, no markdown fences):
{
  "page_num": <integer>,
  "text_blocks": [
    {"type": "heading", "text": "..."},
    {"type": "paragraph", "text": "..."},
    {"type": "list_item", "text": "..."}
  ],
  "tables": [
    {"type": "table", "rows": [["header1", "header2"], ["val1", "val2"]]}
  ],
  "is_blank": false
}

Return ONLY the JSON object — no explanation, no markdown code fences."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def clean_boilerplate(text: str) -> str:
    """Strip known boilerplate patterns from extracted text."""
    for pattern in _BOILERPLATE_RE:
        text = pattern.sub("", text)
    return text.strip()


def parse_gemini_response(raw: str, page_num: int) -> dict:
    """
    Parse Gemini's raw text response into a structured page dict.
    Falls back gracefully if JSON parsing fails.
    """
    if not raw or not raw.strip():
        return {"page_num": page_num, "text_blocks": [], "tables": [], "is_blank": True}

    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        data["page_num"] = page_num  # ensure correct page number
        if "text_blocks" not in data:
            data["text_blocks"] = []
        if "tables" not in data:
            data["tables"] = []
        if "is_blank" not in data:
            data["is_blank"] = len(data["text_blocks"]) == 0 and len(data["tables"]) == 0
        return data
    except json.JSONDecodeError:
        # Fallback: treat entire response as a single paragraph
        logger.warning(f"  [Page {page_num}] JSON parse failed — saving raw text as paragraph")
        return {
            "page_num": page_num,
            "text_blocks": [{"type": "paragraph", "text": cleaned[:5000]}],
            "tables": [],
            "is_blank": False,
        }


def load_existing_output(output_path: Path) -> dict:
    """Load existing JSON if it exists (for resume support)."""
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "source_pdf": "",
        "extraction_engine": "Gemini Flash Vision (IDE Built-in Script)",
        "total_pages": 0,
        "extraction_summary": {
            "total_text_blocks": 0,
            "total_tables": 0,
            "pages_with_content": 0,
            "blank_pages": 0,
            "blank_page_numbers": [],
            "last_extracted_page": 0,
            "status": "in_progress",
        },
        "pages": [],
    }


def save_output(data: dict, output_path: Path):
    """Save current JSON to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_summary(data: dict):
    """Recompute extraction_summary from pages list."""
    total_text = sum(len(p.get("text_blocks", [])) for p in data["pages"])
    total_tables = sum(len(p.get("tables", [])) for p in data["pages"])
    blank_pages = [p["page_num"] for p in data["pages"] if p.get("is_blank", False)]
    last_page = max((p["page_num"] for p in data["pages"]), default=0)

    data["extraction_summary"].update({
        "total_text_blocks": total_text,
        "total_tables": total_tables,
        "pages_with_content": len(data["pages"]) - len(blank_pages),
        "blank_pages": len(blank_pages),
        "blank_page_numbers": blank_pages,
        "last_extracted_page": last_page,
    })


# ── Main extraction loop ───────────────────────────────────────────────────────

def extract_pdf(
    pdf_path: Path,
    output_path: Path,
    start_page: int = 1,
):
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # Count total pages
    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    doc.close()

    print(f"\n{DIVIDER}")
    print(f"  IDE VISION EXTRACT — {pdf_path.name}")
    print(f"  Total pages : {total_pages}")
    print(f"  Output      : {output_path}")
    print(f"  Start page  : {start_page}")
    print(DIVIDER)

    # Load existing progress or create fresh
    data = load_existing_output(output_path)
    data["source_pdf"] = pdf_path.name
    data["total_pages"] = total_pages

    # Build a set of already-extracted page numbers for fast lookup
    extracted_pages = {p["page_num"] for p in data["pages"]}
    logger.info(f"Already extracted: {len(extracted_pages)} pages")

    # Gemini client
    client = get_gemini_client(key_index=0)

    total_start = time.time()
    pages_this_session = 0

    for page_num in range(start_page, total_pages + 1):
        if page_num in extracted_pages:
            logger.info(f"  [Page {page_num}/{total_pages}] Already extracted — skipping")
            continue

        print(f"\n  [Page {page_num}/{total_pages}]", end=" ", flush=True)

        # Render page to JPEG bytes in-memory (no disk write)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                t0 = time.time()
                jpeg_bytes = render_page_to_jpeg(pdf_path, page_num)
                raw_response = call_gemini(client, jpeg_bytes, EXTRACTION_PROMPT)
                elapsed = time.time() - t0

                page_data = parse_gemini_response(raw_response, page_num)

                n_blocks = len(page_data.get("text_blocks", []))
                n_tables = len(page_data.get("tables", []))
                is_blank = page_data.get("is_blank", False)

                status = "BLANK" if is_blank else f"{n_blocks} blocks, {n_tables} tables"
                print(f"{status} ({elapsed:.1f}s)")

                data["pages"].append(page_data)
                extracted_pages.add(page_num)
                pages_this_session += 1
                break

            except Exception as exc:
                if attempt < MAX_RETRIES:
                    print(f"[retry {attempt}/{MAX_RETRIES}] {exc}")
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    print(f"[FAILED after {MAX_RETRIES} attempts] {exc}")
                    # Save a failure placeholder
                    data["pages"].append({
                        "page_num": page_num,
                        "text_blocks": [],
                        "tables": [],
                        "is_blank": False,
                        "extraction_error": str(exc),
                    })
                    extracted_pages.add(page_num)

        # Periodic save every SAVE_EVERY pages
        if pages_this_session % SAVE_EVERY == 0:
            update_summary(data)
            data["extraction_summary"]["status"] = "in_progress"
            save_output(data, output_path)
            logger.info(f"  [Checkpoint] Saved progress at page {page_num}")

    # Sort pages by page_num before final save
    data["pages"].sort(key=lambda p: p["page_num"])

    # Final save
    update_summary(data)
    data["extraction_summary"]["status"] = "complete"
    save_output(data, output_path)

    total_elapsed = time.time() - total_start
    print(f"\n{DIVIDER}")
    print(f"  EXTRACTION COMPLETE")
    print(f"  Pages extracted  : {len(data['pages'])}")
    print(f"  Text blocks      : {data['extraction_summary']['total_text_blocks']}")
    print(f"  Tables           : {data['extraction_summary']['total_tables']}")
    print(f"  Blank pages      : {data['extraction_summary']['blank_pages']}")
    print(f"  Time             : {total_elapsed/60:.1f} min")
    print(f"  Output saved to  : {output_path}")
    print(DIVIDER)
    print(f"\nNext step — Run ingestion:")
    print(f"  python ide_gemini_ingest.py {output_path} --pdf \"{pdf_path}\" --classification Anthropology")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF pages using Gemini Flash Vision (no disk images, direct in-memory rendering)"
    )
    parser.add_argument("--pdf",        default=str(DEFAULT_PDF),    help="Path to PDF file")
    parser.add_argument("--output",     default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--start-page", type=int, default=1,         help="Start from this page (for resume)")
    args = parser.parse_args()

    extract_pdf(
        pdf_path=Path(args.pdf),
        output_path=Path(args.output),
        start_page=args.start_page,
    )


if __name__ == "__main__":
    main()
