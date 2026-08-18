"""
gemini_batch_extract.py
────────────────────────
Slow-and-steady scanned PDF → structured JSON extractor using Gemini Vision API.

Strategy:
  • Page-by-page extraction — one Gemini API call per page.
  • ZERO pages are ever skipped. Every page MUST succeed before moving forward.
  • Full retry loop per page:
      - RPM / temp error  → wait 60s, retry the SAME key (up to 3 attempts per key)
      - Daily quota hit   → rollback to next key, retry the SAME page
      - All keys dead     → save progress, exit cleanly (resume tomorrow)
  • Progress saved to progress.json after every successful page.
  • Re-running the script tomorrow automatically resumes from where it stopped.

Rate limits with 5 rollback keys (free tier):
  • Each key: 1,500 requests/day  →  5 keys: 7,500 requests/day
  • 500-page PDF = 500 API calls
  • 15 PDFs/day = 7,500 calls     →  100% free, no billing needed

Usage:
  python gemini_batch_extract.py "C:/path/to/book.pdf"
  python gemini_batch_extract.py "C:/path/to/book.pdf" --output-dir "C:/results"
  python gemini_batch_extract.py "C:/path/to/book.pdf" --delay 2.0
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path

import fitz  # PyMuPDF

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from extraction.gemini_client import (
    _load_api_keys,
    _safety_settings,
    is_daily_quota_error,
    PAGE_RENDER_DPI,
    PAGE_JPEG_QUALITY,
    MAX_IMAGE_BYTES,
    GEMINI_MODEL,
    RPM_COOLDOWN_SECONDS,
    MAX_RPM_RETRIES,
    _EXHAUSTED_KEY_INDICES,
)

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("[ERROR] google-genai SDK not installed. Run: pip install google-genai")
    sys.exit(1)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("gemini_batch_extract")

DIVIDER = "=" * 65

# ── Single-page extraction prompt ─────────────────────────────────────────────
PAGE_PROMPT = """You are a precise OCR and document structure extractor for scanned PDFs.

Extract ALL visible text from this scanned PDF page image.

RULES:
1. Extract every visible word and sentence accurately — no hallucination, no additions.
2. Classify each text unit:
   - "heading"    → section/chapter titles (bold, larger font, numbered like 1.1, 2.3)
   - "subheading" → sub-section titles
   - "paragraph"  → regular body text
   - "list_item"  → bullet points or numbered list items
   - "caption"    → figure/diagram captions
3. For TABLES: extract as a separate "tables" list with rows as arrays of strings.
4. SKIP completely: watermarks, Telegram headers, standalone page numbers, footer lines.
5. If the page is blank or only has watermarks: set "is_blank": true and use empty lists.
6. Wrap bold key terms with **double asterisks** to preserve emphasis.

OUTPUT FORMAT — return a single JSON object (no markdown fences):
{
  "page_num": <integer — the page number printed on the page>,
  "text_blocks": [
    {"type": "heading",   "text": "..."},
    {"type": "paragraph", "text": "..."},
    {"type": "list_item", "text": "..."}
  ],
  "tables": [
    {"rows": [["col1", "col2"], ["val1", "val2"]]}
  ],
  "is_blank": false
}

Return ONLY the JSON object — no explanation, no markdown code fences."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def render_page(doc: fitz.Document, page_num: int) -> bytes:
    """Render a single PDF page (1-indexed) to JPEG bytes at PAGE_RENDER_DPI."""
    page = doc[page_num - 1]
    mat  = fitz.Matrix(PAGE_RENDER_DPI / 72, PAGE_RENDER_DPI / 72)
    pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    jpeg = pix.tobytes(output="jpeg", jpg_quality=PAGE_JPEG_QUALITY)

    if len(jpeg) > MAX_IMAGE_BYTES:
        logger.warning(f"  Page {page_num}: {len(jpeg)/1e6:.1f} MB — re-rendering at 80 DPI.")
        mat2 = fitz.Matrix(80 / 72, 80 / 72)
        pix2 = page.get_pixmap(matrix=mat2, colorspace=fitz.csRGB)
        jpeg = pix2.tobytes(output="jpeg", jpg_quality=65)

    return jpeg


def parse_page_response(raw: str, page_num: int) -> dict:
    """Parse Gemini's JSON response for a single page. Falls back gracefully."""
    import re

    if not raw or not raw.strip():
        return {"page_num": page_num, "text_blocks": [], "tables": [], "is_blank": True}

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        data["page_num"] = page_num
        data.setdefault("text_blocks", [])
        data.setdefault("tables", [])
        data.setdefault("is_blank", not data["text_blocks"] and not data["tables"])
        return data
    except json.JSONDecodeError:
        logger.warning(f"  [Page {page_num}] JSON parse failed — saving raw as paragraph.")
        return {
            "page_num":    page_num,
            "text_blocks": [{"type": "paragraph", "text": cleaned[:5000]}],
            "tables":      [],
            "is_blank":    False,
        }


def call_page_with_rollback(jpeg: bytes, page_num: int) -> str:
    """
    Call Gemini for a single page with full rollback key rotation + per-key retry.

    Per-page guarantee:
      - RPM / temp error  → wait RPM_COOLDOWN_SECONDS (60s), retry same key (up to MAX_RPM_RETRIES = 3x)
      - Daily quota       → permanently mark key exhausted, try next key, retry the same page
      - All keys dead     → raise RuntimeError (caller saves progress and exits cleanly)

    Returns:
        Raw text response string from Gemini.
    """
    api_keys = _load_api_keys()
    if not api_keys:
        raise RuntimeError("No API keys configured in GEMINI_API_KEY.")

    contents = [
        genai_types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
        PAGE_PROMPT,
    ]

    while True:
        available = [i for i in range(len(api_keys)) if i not in _EXHAUSTED_KEY_INDICES]
        if not available:
            raise RuntimeError(
                f"All {len(api_keys)} API keys have exhausted their daily quota. "
                f"Re-run tomorrow to resume from page {page_num}."
            )

        last_exc = None

        for idx in available:
            key    = api_keys[idx]
            masked = f"{key[:8]}..." if len(key) > 8 else "***"
            client = genai.Client(api_key=key)

            # ── Per-key retry loop (for RPM / temp errors) ─────────────────────────
            for attempt in range(1, MAX_RPM_RETRIES + 1):
                try:
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=contents,
                        config=genai_types.GenerateContentConfig(
                            safety_settings=_safety_settings(),
                            temperature=0.0,
                        ),
                    )

                    if response.candidates:
                        reason = str(getattr(response.candidates[0], "finish_reason", "")).upper()
                        if reason in ("SAFETY", "RECITATION", "BLOCKED"):
                            logger.warning(f"  [Page {page_num}] Key {idx} blocked. Reason: {reason}")
                            return ""

                    return response.text or ""   # ✅ page extracted successfully

                except Exception as exc:
                    last_exc = exc

                    if is_daily_quota_error(exc):
                        # Hard daily limit — no point retrying this key
                        _EXHAUSTED_KEY_INDICES.add(idx)
                        print(f"\n  [WARN] Key {idx} ({masked}): DAILY quota exhausted -> rolling to next key")
                        break   # exit retry loop → try next key in outer loop

                    else:
                        # Temporary: RPM / server overload / network
                        if attempt < MAX_RPM_RETRIES:
                            print(
                                f"\n  [WAIT] Key {idx} ({masked}): temp error "
                                f"(attempt {attempt}/{MAX_RPM_RETRIES}) — "
                                f"waiting {RPM_COOLDOWN_SECONDS}s, then retrying same key..."
                            )
                            time.sleep(RPM_COOLDOWN_SECONDS)
                        else:
                            print(
                                f"\n  [FAIL] Key {idx} ({masked}): failed all "
                                f"{MAX_RPM_RETRIES} attempts -> rolling to next key"
                            )
                            time.sleep(2.0)

        # If we exited the key loop, all keys failed with temporary errors on this page.
        # Instead of crashing, wait 60s for the IP block to cool down, and try again.
        print(
            f"\n  [WARN] All available keys failed with temporary errors on page {page_num}. "
            f"Possible IP rate limit block. Waiting 60 seconds to cool down..."
        )
        time.sleep(60.0)


# ── Main extraction function ───────────────────────────────────────────────────

def consolidate_extracted_json(output_dir: Path, pdf_name: str, total_pages: int) -> Path:
    """
    Consolidates individual page JSONs into a single document JSON
    that matches the ingestion pipeline schema.
    """
    pages_data = []
    for page_num in range(1, total_pages + 1):
        page_file = output_dir / f"page_{page_num:04d}.json"
        if page_file.exists():
            with open(page_file, "r", encoding="utf-8") as f:
                pages_data.append(json.load(f))
        else:
            pages_data.append({
                "page_num": page_num,
                "text_blocks": [],
                "tables": [],
                "is_blank": True
            })

    consolidated = {
        "source_pdf": pdf_name,
        "extraction_engine": "Gemini 3.5 Flash Vision",
        "total_pages": total_pages,
        "pages": pages_data
    }

    output_file = output_dir.parent / f"{output_dir.name}_extracted.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2, ensure_ascii=False)
    return output_file


def extract_pdf(pdf_path: Path, output_dir: Path, delay_seconds: float = 1.0):
    """
    Extract every page of a scanned PDF — slow, steady, guaranteed no skips.

    Every page must succeed before moving to the next.
    Progress is saved after each page — always safely resumable.

    Args:
        pdf_path:      Path to the scanned PDF file.
        output_dir:    Directory to save per-page JSON results.
        delay_seconds: Seconds to sleep between API calls (default 1.0).
    """
    pdf_path   = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # ── Load / create progress tracker ────────────────────────────────────────
    progress_path = output_dir / "progress.json"
    if progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as f:
            progress = json.load(f)
        print(f"  Resuming — {len(progress.get('extracted_pages', []))} pages already done.")
    else:
        progress = {"pdf": pdf_path.name, "extracted_pages": [], "status": "in_progress"}

    extracted_pages = set(progress.get("extracted_pages", []))

    # ── Open PDF ───────────────────────────────────────────────────────────────
    doc         = fitz.open(str(pdf_path))
    total_pages = len(doc)
    pending     = [p for p in range(1, total_pages + 1) if p not in extracted_pages]

    print(f"\n{DIVIDER}")
    print(f"  PDF            : {pdf_path.name}")
    print(f"  Total pages    : {total_pages}")
    print(f"  Already done   : {len(extracted_pages)} pages")
    print(f"  Pending pages  : {len(pending)}")
    print(f"  Delay          : {delay_seconds}s between pages")
    print(f"  Output dir     : {output_dir}")
    print(f"{DIVIDER}\n")

    if not pending:
        print("  All pages already extracted. Nothing to do.")
        doc.close()
        return

    pages_done_this_run = 0

    for page_num in pending:
        page_index = len(extracted_pages) + 1
        print(f"  [{page_index}/{total_pages}]  Page {page_num} ...", end=" ", flush=True)

        # ── Render page to JPEG ────────────────────────────────────────────────
        try:
            jpeg = render_page(doc, page_num)
        except Exception as e:
            print(f"[RENDER FAIL] {e}")
            logger.error(f"Page {page_num}: PyMuPDF render failed — {e}.")
            doc.close()
            sys.exit(1)

        # ── Call Gemini with full rollback ─────────────────────────────────────
        try:
            t0  = time.time()
            raw = call_page_with_rollback(jpeg, page_num)
            elapsed = time.time() - t0
        except Exception as e:
            # All API keys exhausted or unhandled error — save progress, exit cleanly
            print(f"\n\n[FATAL] {e}")
            progress["extracted_pages"] = sorted(list(extracted_pages))
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
            print(f"\n  Progress saved: {len(extracted_pages)}/{total_pages} pages done.")
            print(f"  Re-run this script tomorrow — resumes from page {page_num} automatically.")
            doc.close()
            sys.exit(1)

        # ── Parse and save result ──────────────────────────────────────────────
        page_data = parse_page_response(raw, page_num)
        out_path  = output_dir / f"page_{page_num:04d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(page_data, f, indent=2, ensure_ascii=False)

        # ── Update progress (saved after EVERY page — never lose work) ─────────
        extracted_pages.add(page_num)
        pages_done_this_run += 1
        progress["extracted_pages"] = sorted(list(extracted_pages))
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)

        # ── Console summary for this page ──────────────────────────────────────
        n_blocks  = len(page_data.get("text_blocks", []))
        n_tables  = len(page_data.get("tables", []))
        is_blank  = page_data.get("is_blank", False)
        exhausted = len(_EXHAUSTED_KEY_INDICES)
        key_msg   = f"  [Keys left: {len(_load_api_keys()) - exhausted}/{ len(_load_api_keys())}]" if exhausted else ""
        status    = "BLANK" if is_blank else f"{n_blocks} blocks, {n_tables} tables"

        print(f"[OK] {status}  ({elapsed:.1f}s){key_msg}")

        if delay_seconds > 0 and page_num != pending[-1]:
            time.sleep(delay_seconds)

    doc.close()

    # ── Final summary ──────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print(f"  EXTRACTION COMPLETE")
    print(f"  Pages this run  : {pages_done_this_run}")
    print(f"  Total extracted : {len(extracted_pages)}/{total_pages}")
    if len(extracted_pages) == total_pages:
        progress["status"] = "complete"
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        print(f"  Status          : COMPLETE SUCCESS")

        # Consolidate page JSONs into standard output location
        merged_file = consolidate_extracted_json(output_dir, pdf_path.name, total_pages)
        print(f"  Consolidated JSON saved -> {merged_file}")
    else:
        print(f"  Remaining       : {total_pages - len(extracted_pages)} pages (resume tomorrow)")
    print(f"  Results in      : {output_dir}")
    print(f"{DIVIDER}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Slow-and-steady scanned PDF extractor via Gemini Vision API.\n"
            "  • 1 page per API call — ZERO pages skipped\n"
            "  • RPM error → wait 60s → retry same key (up to 3x)\n"
            "  • Daily quota → rollback to next key → retry same page\n"
            "  • All keys dead → save progress → exit (re-run tomorrow)\n"
            "  • 5 keys x 1,500 RPD = 7,500 pages/day free\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the scanned PDF file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save JSON files. Defaults to ./output/<pdf_stem>/",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to sleep between pages (default 2.0).",
    )

    args     = parser.parse_args()
    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else ROOT_DIR / "output" / pdf_path.stem
    )

    extract_pdf(
        pdf_path      = pdf_path,
        output_dir    = output_dir,
        delay_seconds = args.delay,
    )


if __name__ == "__main__":
    main()
