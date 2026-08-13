"""
gemini_client.py
─────────────────
Shared utilities used by text_service.py and table_service.py.

Responsibilities:
  - Initialise the google-genai Client from GEMINI_API_KEY env variable.
  - Render a single PDF page to JPEG bytes using PyMuPDF (fitz).
  - Send an image + prompt to Gemini 2.5 Flash and return the raw text response.

Usage:
    from extraction.gemini_client import render_page_to_jpeg, call_gemini
"""

import os
import re
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger("gemini_client")

# ── Model ─────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.5-flash"

# Module-level cache to remember key indices that hit hard daily limits
_EXHAUSTED_KEY_INDICES = set()

def is_daily_quota_error(exc: Exception) -> bool:
    """
    Check if the exception is due to daily request limits (exhausted for the day)
    vs a temporary requests-per-minute (RPM) rate limit.
    """
    err_str = str(exc).lower()
    if "requestsperday" in err_str or "daily" in err_str or "day" in err_str:
        return True
    if "generate_content_free_tier_requests" in err_str and "minute" not in err_str:
        return True
    return False

# ── SDK import (optional dependency — fails gracefully) ───────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning(
        "google-genai SDK not installed. "
        "Run: pip install google-genai"
    )

# ── Page render settings ──────────────────────────────────────────────────────
PAGE_RENDER_DPI   = 150          # DPI for page-to-image render (balance: quality vs token size)
PAGE_JPEG_QUALITY = 85           # JPEG compression quality (0-100)
MAX_IMAGE_BYTES   = 19 * 1024 * 1024  # 19 MB — stay under Gemini's 20 MB inline limit


# ── Client factory ─────────────────────────────────────────────────────────────

def get_gemini_client(key_index: int = 0):
    """
    Build and return a google.genai.Client using GEMINI_API_KEY from env.
    Supports comma/semicolon separated keys for failover rotation.

    Raises:
        ImportError:  If google-genai SDK is not installed.
        RuntimeError: If GEMINI_API_KEY is not set or is the placeholder value.
    """
    if not GENAI_AVAILABLE:
        raise ImportError(
            "google-genai SDK not installed. Run: pip install google-genai"
        )

    raw_keys = os.environ.get("GEMINI_API_KEY", "").strip()
    api_keys = [k.strip() for k in re.split(r"[,;]", raw_keys) if k.strip()]

    if not api_keys or api_keys[0] == "your_gemini_api_key_here":
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file:\n"
            "  GEMINI_API_KEY=AIzaSy..."
        )

    # Wrap the index to loop safely through the list of keys
    selected_key = api_keys[key_index % len(api_keys)]
    return genai.Client(api_key=selected_key)


# ── Page renderer ──────────────────────────────────────────────────────────────

def render_page_to_jpeg(pdf_path: Path, page_number: int) -> bytes:
    """
    Render a single PDF page to JPEG bytes using PyMuPDF.

    Args:
        pdf_path:    Path to the PDF file.
        page_number: 1-indexed page number.

    Returns:
        JPEG image as bytes.

    Raises:
        ValueError:       If page_number is out of range.
        FileNotFoundError: If pdf_path does not exist.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    if page_number < 1 or page_number > total_pages:
        doc.close()
        raise ValueError(
            f"page_number={page_number} is out of range "
            f"(PDF has {total_pages} pages)."
        )

    page = doc[page_number - 1]
    mat  = fitz.Matrix(PAGE_RENDER_DPI / 72, PAGE_RENDER_DPI / 72)
    pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)

    jpeg_bytes = pix.tobytes(output="jpeg", jpg_quality=PAGE_JPEG_QUALITY)

    doc.close()

    # Guard against exceeding Gemini inline image limit
    if len(jpeg_bytes) > MAX_IMAGE_BYTES:
        logger.warning(
            f"Page {page_number} image is {len(jpeg_bytes) / 1e6:.1f} MB — "
            f"exceeds {MAX_IMAGE_BYTES / 1e6:.0f} MB limit. "
            f"Re-rendering at 100 DPI."
        )
        doc2 = fitz.open(str(pdf_path))
        mat2 = fitz.Matrix(100 / 72, 100 / 72)
        pix2 = doc2[page_number - 1].get_pixmap(matrix=mat2, colorspace=fitz.csRGB)
        jpeg_bytes = pix2.tobytes(output="jpeg", jpg_quality=75)
        doc2.close()

    return jpeg_bytes


# ── Gemini API caller ──────────────────────────────────────────────────────────

def call_gemini(client, image_bytes: bytes, prompt: str) -> str:
    """
    Send a JPEG image + text prompt to Gemini 3.5 Flash and return raw text.
    Automatically rotates to alternative API keys in GEMINI_API_KEY if the call fails.
    Remembers and bypasses keys that have exhausted their daily quota.

    Args:
        client:      A google.genai.Client instance (from get_gemini_client()).
        image_bytes: JPEG bytes of the rendered page.
        prompt:      Instruction text for Gemini.

    Returns:
        Raw text response from Gemini (may be JSON string, or empty on block).
    """
    raw_keys = os.environ.get("GEMINI_API_KEY", "").strip()
    api_keys = [k.strip() for k in re.split(r"[,;]", raw_keys) if k.strip()]
    if not api_keys:
        api_keys = [""]

    last_exception = None

    # Get non-exhausted indices
    available_indices = [i for i in range(len(api_keys)) if i not in _EXHAUSTED_KEY_INDICES]
    if not available_indices:
        logger.error(f"[gemini_client] All {len(api_keys)} configured API keys have hit their daily quota.")
        raise RuntimeError("All configured API keys have exhausted their daily quota.")

    for idx in available_indices:
        key = api_keys[idx]
        try:
            # Use passed client for first attempt (if key 0 is not exhausted), otherwise build new client
            active_client = client if (idx == 0 and 0 not in _EXHAUSTED_KEY_INDICES) else get_gemini_client(key_index=idx)

            response = active_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg",
                    ),
                    prompt,
                ],
                config=genai_types.GenerateContentConfig(
                    safety_settings=[
                        genai_types.SafetySetting(
                            category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai_types.SafetySetting(
                            category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai_types.SafetySetting(
                            category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai_types.SafetySetting(
                            category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                    ],
                    temperature=0.0,   # deterministic output for extraction
                ),
            )

            # Check finish reason for safety blocks
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = str(getattr(candidate, "finish_reason", "")).upper()
                if finish_reason in ("SAFETY", "RECITATION", "BLOCKED"):
                    logger.warning(
                        f"Gemini blocked response. Finish reason: {finish_reason}"
                    )
                    return ""

            return response.text or ""

        except Exception as exc:
            last_exception = exc
            masked_key = f"{key[:8]}..." if len(key) > 8 else "..."

            if is_daily_quota_error(exc):
                _EXHAUSTED_KEY_INDICES.add(idx)
                logger.warning(
                    f"[gemini_client] Key index {idx} ({masked_key}) hit daily quota limit. "
                    f"Marking as permanently exhausted for this session."
                )
            else:
                logger.warning(
                    f"[gemini_client] Key index {idx} ({masked_key}) failed temporarily (e.g. rate limit). "
                    f"Error: {exc}. Key remains active for future pages."
                )
            continue

    # If all keys failed, raise the last exception
    logger.error(f"[gemini_client] All available API keys failed for model {GEMINI_MODEL}.")
    raise last_exception or RuntimeError("All API keys failed.")
