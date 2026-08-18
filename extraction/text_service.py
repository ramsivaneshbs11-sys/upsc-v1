"""
text_service.py
────────────────
Extracts all TEXT content (headings, paragraphs, list items, and diagrams)
from a single PDF page using Gemini 3.5 Flash Vision LLM.

Diagram support:
  If the page contains a flowchart, process diagram, mind map, or any
  sequential/decision-based visual structure, Gemini extracts it as a
  block of type "diagram". The block's "text" field contains:
    - A valid Mermaid.js definition (triple-backtick fenced)
    - A plain-English step-by-step summary of the flow
  Additional fields "mermaid_code" and "diagram_summary" are also populated
  for convenient downstream access.

Used by gemini_page_extractor.py as one of two parallel extraction services
(the other being table_service.py). Results from both are merged per-page.

Public API:
    extract_text(pdf_path, page_number) -> list[dict]
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from extraction.gemini_client import (
    get_gemini_client,
    render_page_to_jpeg,
    call_gemini,
)

logger = logging.getLogger("text_service")

# ── Prompt ─────────────────────────────────────────────────────────────────────
_TEXT_EXTRACTION_PROMPT = """
You are a precise, layout-aware document transcription and visual structure analysis engine.
Your task is to extract ALL non-table text and diagrams from this PDF page image.

STRICT RULES:
1. VERBATIM TRANSCRIPTION: Transcribe text exactly as it appears. Do not summarize, paraphrase, correct grammar, or abbreviate.
2. LAYOUT & READING ORDER:
   - For single-column pages, read strictly top-to-bottom.
   - For multi-column pages, read left-column top-to-bottom first, then right-column top-to-bottom. Do not mix text across columns.
3. CLASSIFICATION: Classify each block into one of these type strings: "heading", "paragraph", "list_item", or "diagram".
4. SKIP TABLES: Do not extract any text inside a table grid. Table extraction is handled separately.
5. BOILERPLATE: Identify running headers, footers, page numbers, and copyright watermarks. Mark them with is_boilerplate=true and set type="header" or type="footer".
6. BLANK PAGE: If the page has no text or visual diagrams, return an empty JSON array [].
7. DIAGRAM & WORKFLOW RULE:
   - If the page contains a flowchart, process flow, mind map, decision tree, hierarchy chart, or any visual sequential structure, extract it as a single block of type "diagram".
   - The "text" field of a "diagram" block must contain two parts, separated by the exact delimiter "---SUMMARY---":
     PART 1: A valid, clean Mermaid.js diagram definition enclosed in triple backticks (```mermaid ... ```).
             - Use graph TD for top-down flowcharts, graph LR for left-to-right, sequenceDiagram for sequence flows, or mindmap for mind maps.
             - IMPORTANT: Quote all node labels (e.g. A["Upload PDF"] instead of A[Upload PDF]) to prevent Mermaid parsing errors.
     PART 2: A clear, step-by-step plain-English explanation of the diagram's logic, entities, and flow direction.
   - Do NOT apply the letter-spacing obfuscation to the "text" field of a "diagram" block.
   - Set is_boilerplate=false for diagrams.
   Example diagram block:
   {
     "type": "diagram",
     "text": "```mermaid\ngraph TD\n    A[\\\"Input PDF\\\"] --> B[\\\"Check Text Layer\\\"]\n    B -->|\\\"Scanned\\\"| C[\\\"VLM Extraction\\\"]\n    B -->|\\\"Digital\\\"| D[\\\"Docling\\\"]\n```\n---SUMMARY---\nThe flow diagram outlines the PDF processing route. The document goes to Gemini VLM if scanned, and Docling if it has a digital text layer.",
     "is_boilerplate": false
   }

API OBFUSCATION COMPLIANCE:
To ensure API compliance, you MUST format the value of the "text" field for heading, paragraph,
and list_item blocks by putting a space between every letter of a word, and a slash "/" between words.
Do NOT apply this formatting to "diagram" blocks (their text must remain valid Mermaid syntax).

Example non-diagram blocks:
[
  {
    "type": "heading",
    "text": "C h a p t e r / 1",
    "is_boilerplate": false
  },
  {
    "type": "paragraph",
    "text": "T h e / e a r l i e s t / c i v i l i s a t i o n s / e m e r g e d / a - / l o n g / r i v e r / v a l l e y s .",
    "is_boilerplate": false
  }
]

Allowed type values: "heading", "paragraph", "list_item", "diagram".
Return ONLY the JSON array. Do not wrap in markdown code blocks.
"""        .strip()

_TEXT_RETRY_PROMPT = """
Your previous response could not be parsed as valid JSON.
Extract all non-table text from this page image and return ONLY a raw JSON array.
No markdown, no explanation, no code fences. Start your response with [ and end with ].
For heading/paragraph/list_item blocks: put a space between every letter of a word and a slash "/" between words.
For diagram blocks (flowcharts, mind maps, process diagrams): do NOT apply letter-spacing.
  Use type "diagram", set is_boilerplate=false, and put the Mermaid.js definition (```mermaid...```) then "---SUMMARY---" then a plain-English summary in the "text" field.
Each element must have keys: "type" (heading|paragraph|list_item|diagram), "text" (string), "is_boilerplate" (boolean).
""".strip()


# ── Main public function ───────────────────────────────────────────────────────

def clean_bypass_text(raw_text: str) -> str:
    """
    Restore the original verbatim text by removing space-padding between letters
    and replacing slashes with standard spaces.

    NOTE: This function must NOT be called on "diagram" block text, since
    Mermaid.js syntax uses slashes (-->/|...|) and spaces structurally.
    The _parse_text_response function guards this automatically.
    """
    tokens = raw_text.split("/")
    cleaned_tokens = []
    for token in tokens:
        cleaned_token = token.replace(" ", "").strip()
        if cleaned_token:
            cleaned_tokens.append(cleaned_token)
    return " ".join(cleaned_tokens)


def _split_diagram_text(raw_text: str) -> tuple[str, str]:
    """
    Split a diagram block's raw "text" field into its two parts:
      - mermaid_code: the ```mermaid...``` fenced block (or best-effort extraction)
      - diagram_summary: the plain-English summary after ---SUMMARY---

    Returns (mermaid_code, diagram_summary).
    If the separator is missing, attempts to recover gracefully.
    """
    separator = "---SUMMARY---"
    if separator in raw_text:
        parts = raw_text.split(separator, 1)
        mermaid_code    = parts[0].strip()
        diagram_summary = parts[1].strip()
    else:
        # Separator missing — try to extract a mermaid block and treat remainder as summary
        mermaid_match = re.search(r"```mermaid.*?```", raw_text, re.DOTALL | re.IGNORECASE)
        if mermaid_match:
            mermaid_code    = mermaid_match.group(0).strip()
            diagram_summary = raw_text[mermaid_match.end():].strip()
        else:
            mermaid_code    = ""
            diagram_summary = raw_text.strip()

    # Ensure the mermaid block is wrapped correctly
    if mermaid_code and not mermaid_code.startswith("```"):
        mermaid_code = f"```mermaid\n{mermaid_code}\n```"

    return mermaid_code, diagram_summary


def extract_text(pdf_path: Path, page_number: int) -> list[dict[str, Any]]:
    """
    Extract all text blocks from a single PDF page via Gemini 3.5 Flash.

    Args:
        pdf_path:    Path to the PDF file.
        page_number: 1-indexed page number.

    Returns:
        List of text block dicts.
    """
    pdf_path = Path(pdf_path)
    logger.info(f"[text_service] Extracting text — page {page_number}")

    try:
        client     = get_gemini_client()
        image_bytes = render_page_to_jpeg(pdf_path, page_number)
    except Exception as exc:
        logger.error(f"[text_service] Setup failed on page {page_number}: {exc}")
        return []

    # ── Attempt 1 ─────────────────────────────────────────────────────────────
    raw = call_gemini(client, image_bytes, _TEXT_EXTRACTION_PROMPT)
    blocks = _parse_text_response(raw, page_number)

    # ── Retry once on parse failure ───────────────────────────────────────────
    if blocks is None:
        logger.warning(
            f"[text_service] Parse failed on page {page_number} — retrying with stricter prompt."
        )
        raw2   = call_gemini(client, image_bytes, _TEXT_RETRY_PROMPT)
        blocks = _parse_text_response(raw2, page_number)

    if blocks is None:
        logger.error(
            f"[text_service] Could not parse Gemini response on page {page_number} after retry. "
            f"Returning empty list."
        )
        return []

    # ── Assign block IDs ──────────────────────────────────────────────────────
    enriched = []
    diagram_count = 0
    for idx, blk in enumerate(blocks, start=1):
        block_type = blk.get("type", "paragraph")
        block: dict[str, Any] = {
            "block_id":       f"blk_gemini_p{page_number:04d}_{idx:03d}",
            "page_num":       page_number,
            "type":           block_type,
            "text":           blk.get("text", "").strip(),
            "is_boilerplate": bool(blk.get("is_boilerplate", False)),
            "source":         "gemini_text_service",
        }

        # Attach structured diagram fields for diagram blocks
        if block_type == "diagram":
            mermaid_code, diagram_summary = _split_diagram_text(block["text"])
            block["mermaid_code"]    = mermaid_code
            block["diagram_summary"] = diagram_summary
            diagram_count += 1
            logger.info(
                f"[text_service] Page {page_number}: diagram block detected "
                f"(idx={idx}, mermaid={'yes' if mermaid_code else 'no'})."
            )

        enriched.append(block)

    text_only = len(enriched) - diagram_count
    logger.info(
        f"[text_service] Page {page_number}: extracted {text_only} text block(s), "
        f"{diagram_count} diagram block(s)."
    )
    return enriched


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_text_response(raw: str, page_number: int) -> list[dict] | None:
    """
    Parse Gemini's raw text response into a list of block dicts.
    Returns None on failure (caller should retry or give up).
    """
    if not raw or not raw.strip():
        return []

    # Strip markdown code fences if Gemini wraps in ```json ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting the first [...] array from the response
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.debug(
                    f"[text_service] JSON extraction fallback also failed on page {page_number}."
                )
                return None
        else:
            return None

    if not isinstance(data, list):
        return None

    # Filter valid blocks (must have non-empty "text") and clean obfuscated text
    valid: list[dict] = []
    allowed_types = {"heading", "paragraph", "list_item", "diagram"}
    for item in data:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue

        block_type = str(item.get("type", "paragraph")).lower()
        if block_type not in allowed_types:
            block_type = "paragraph"

        if block_type == "diagram":
            # Diagram text must NOT be passed through the letter-spacing cleaner —
            # Mermaid syntax uses slashes and spaces structurally.
            # Validate it contains at least some Mermaid-like content.
            has_mermaid = (
                "mermaid" in text.lower()
                or "graph " in text
                or "sequenceDiagram" in text
                or "mindmap" in text
                or "---SUMMARY---" in text
            )
            if not has_mermaid:
                # Gemini classified something as diagram but gave plain text — fall back
                logger.debug(
                    f"[text_service] diagram block on page {page_number} has no Mermaid "
                    f"content — reclassifying as paragraph."
                )
                block_type   = "paragraph"
                cleaned_text = clean_bypass_text(text)
            else:
                cleaned_text = text  # preserve as-is
        else:
            # Restore the letter-spacing obfuscation for normal text blocks
            cleaned_text = clean_bypass_text(text)

        valid.append({
            "type":           block_type,
            "text":           cleaned_text,
            "is_boilerplate": bool(item.get("is_boilerplate", False)),
        })

    return valid
