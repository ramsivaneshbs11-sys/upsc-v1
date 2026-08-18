"""
boilerplate_detector.py
─────────────────────────
Detects and tags boilerplate text in UPSC study material.

Boilerplate types detected:
  1. Header / Running Title
     - Standard header phrases: "UPSC Civil Services", "General Studies", "IGNOU", etc.
     - Document title repetitions on every page.
  2. Footer / Page Number
     - "Page X of Y", "Page X", bare numbers at top/bottom margin.
  3. Publisher / Copyright Notice
     - "All Rights Reserved", "For internal use only", website URLs, phone numbers.
     NOTE: Academic bibliography/reference entries are NOT classified as copyright.
  4. Table of Contents / Index Line
     - Lines of dots leading to a page number (e.g. "Chapter 1 ........ 12").
     - ToC page number tokens are classified as "toc_page_number".   [Issue #2]
  5. Watermark / Background Text
     - Common overlay phrases: "DRAFT", "CONFIDENTIAL", "SAMPLE ONLY".
  6. Bibliography / Reference Entry                                   [Issue #8]
     - Academic citation entries (Author. Year. Title...) retained with is_boilerplate=False
  7. Exercise Headings                                                [Issue #9]
     - "Check Your Progress" sections tagged as "exercise_heading", NOT stripped

Output field added to block dicts:
  "is_boilerplate": bool
  "boilerplate_type": str | None   ("header" | "footer" | "copyright" | "toc" |
                                    "toc_page_number" | "watermark" | "bibliography" |
                                    "exercise_heading" | "repeating_header_footer")
"""

import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("boilerplate_detector")

# ── 1. PATTERN DEFINITIONS ────────────────────────────────────────────────────

HEADER_PATTERNS = [
    r"(?i)^\s*upsc\s+(civil\s+services|prelims|mains|examination)",
    r"(?i)^\s*general\s+studies\s*[-–:]?\s*paper\s+[i|v|x\d]+",
    r"(?i)^\s*egyankosh\s*\|\s*ignou",
    r"(?i)^\s*subject\s*:\s*(history|geography|polity|economy|anthropology)",
    r"(?i)^\s*module\s+\d+\s*[-–:]?\s*",
    r"(?i)^\s*chapter\s+\d+\s*[-–:]?\s*$",
    r"(?i)^\s*vision\s+ias\s*",
    r"(?i)^\s*drishti\s+ias\s*",
    r"(?i)^\s*insights\s+on\s+india\s*",
    r"(?i)^\s*forum\s+ias\s*",
    r"(?i)^\s*byju'?s\s+classes\s*",
    # Running unit/chapter titles in UPSC IGNOU booklets:
    # These short titles appear at the top or bottom margin of every page and
    # should be stripped out of the body text stream.
    r"(?i)^\s*violence\s+and\s+repression\s*$",
    r"(?i)^\s*modern\s+warfare\s*$",
    r"(?i)^\s*total\s+war\s*$",
    r"(?i)^\s*violence\s+by\s+non[-\s]state\s+actors\s*$",
    r"(?i)^\s*unit\s+\d+\s*$",                # bare "Unit 27" style running header
    r"(?i)^\s*block[-\s]\d+\s*$",             # bare "Block-8" style running header
    # ── Issue D: IGNOU watermark / logo text ─────────────────────────────────
    # "ignou THE PEOPLE'S UNIVERSITY" and variants appear as watermark or
    # background logo text extracted onto every page of IGNOU course booklets.
    r"(?i)^\s*ignou\s+the\s+people[''']?s\s+university\s*$",
    r"(?i)^\s*the\s+people[''']?s\s+university\s*$",
    r"(?i)^\s*ignou\s*$",                      # standalone IGNOU logo text
]

FOOTER_PATTERNS = [
    r"(?i)^\s*page\s+\d+\s*(of\s+\d+)?\s*$",
    r"^\s*\d+\s*/\s*\d+\s*$",
    r"^\s*-\s*\d+\s*-\s*$",
    r"^\s*\[\s*\d+\s*\]\s*$",
    r"^\s*\d+\s*$",                            # bare page number line
    r"(?i)^\s*continued\s+on\s+next\s+page",
    r"(?i)^\s*turn\s+over\s*$",
    r"(?i)^\s*pto\s*$",
]

COPYRIGHT_PATTERNS = [
    r"(?i)all\s+rights?\s+reserved",
    r"(?i)copyright\s*(©|\(c\))?\s*\d{4}",
    r"(?i)for\s+(internal|personal)\s+use\s+only",
    r"(?i)do\s+not\s+(copy|duplicate|reproduce|distribute)",
    r"(?i)no\s+part\s+of\s+this\s+(publication|document)\s+may\s+be",
    r"(?i)www\.[a-z0-9\-]+\.[a-z]{2,}",
    r"(?i)email\s*:\s*[^\s]+@[^\s]+",
    r"(?i)call\s*/?s*whatsapp\s*:\s*\+?\d[\d\s\-]{8,}",
    r"(?i)contact\s*:\s*\+?\d[\d\s\-]{8,}",
    # NOTE: https?:// URLs are intentionally NOT included here —
    #       academic bibliography entries often contain DOI/URL links.
    #       URL detection is handled via a separate pass with context-awareness.
]

# ── Issue #8: Bibliography / Reference Entry Detection ───────────────────────
# Academic citations typically start with: Author surname, Firstname. Year.
# They are NOT boilerplate — they are valid scholarly metadata.
# These patterns identify citation-style strings so we can AVOID mis-classifying them.
BIBLIOGRAPHY_PATTERNS = [
    # "Surname, Firstname. 1999." — standard academic citation format
    r"^[A-Z][a-zA-Z\-]+,\s+[A-Z][a-zA-Z\s\.]+\.\s+\d{4}\.",
    # "Author. Year. 'Title'" — common variation
    r"^[A-Z][a-zA-Z\s\-]+\.\s+\d{4}\.\s+['\"\u2018\u2019\u201c\u201d]",
    # DOI pattern — starts with "doi:" or "https://doi.org"
    r"(?i)^doi\s*:\s*(10\.\d{4,})",
    r"(?i)https?://doi\.org/",
    r"(?i)https?://dx\.doi\.org/",
    r"(?i)https?://[a-z]+\.jstor\.org/stable/",
    r"(?i)https?://[a-z]+\.luminosoa\.org/",
    # Academic journal title patterns (common indicators that this is a reference)
    r"(?i)\bProceedings\s+of\s+the\s+Indian\s+History\s+Congress\b",
    r"(?i)\bModern\s+Asian\s+Studies\b",
    r"(?i)\bThe\s+Journal\s+of\s+Asian\s+Studies\b",
]

# ── Issue #9: Exercise Heading Detection ─────────────────────────────────────
# "Check Your Progress" sections are pedagogical content, NOT boilerplate.
# They should be tagged but NOT suppressed (is_boilerplate remains False).
EXERCISE_HEADING_PATTERNS = [
    r"(?i)^\s*check\s+your\s+progress\s*[-–]?\s*\d*\s*$",
    r"(?i)^\s*intext\s+questions?\s*\d*\s*$",
    r"(?i)^\s*self\s+assessment\s+questions?\s*\d*\s*$",
    r"(?i)^\s*activity\s+\d+\s*$",
    r"(?i)^\s*terminal\s+questions?\s*$",
]

TOC_PATTERNS = [
    r"\.{4,}\s*\d+\s*$",                       # Dots leading to page number: "Intro ...... 5"
    r"_{4,}\s*\d+\s*$",                        # Underscores leading to number
    r"(?i)^\s*contents\s*$",
    r"(?i)^\s*table\s+of\s+contents\s*$",
    # ── Issue I: IGNOU TOC entries — "Unit 4 Demographic Data 205" style ────
    # Lines where the last token is a 2-3 digit page number, and preceding
    # text is 5-80 chars (unit/section names). Avoids false-positives on
    # normal paragraph text ending with a year (4 digits).
    r"^.{5,80}\s+\d{2,3}\s*$",
    r"(?i)^\s*course\s+contents\s*$",
    r"(?i)^\s*pages?\s*$",                     # standalone "Pages" header on TOC page
]

WATERMARK_PATTERNS = [
    r"(?i)^\s*draft\s*$",
    r"(?i)^\s*confidential\s*$",
    r"(?i)^\s*sample\s+only\s*$",
    r"(?i)^\s*for\s+review\s+only\s*$",
    r"(?i)^\s*not\s+for\s+sale\s*$",
    # ── Enhanced Option 2: IGNOU partial-bleed watermark block variants ──────
    # These fragments appear when the IGNOU background logo is only partially
    # captured by Docling — e.g. just "PEOPLE'S" or "HE PEOPLE'S OPLE'S".
    r"(?i)^\s*people[''']?s\s*$",
    r"(?i)^\s*ople[''']?s\s*$",
    r"(?i)^\s*he\s+people[''']?s\s+ople[''']?s\s*$",
    r"(?i)^\s*he\s+people[''']?s\s*$",
    r"(?i)^\s*university\s*$",                    # standalone "UNIVERSITY" watermark
    r"(?i)^\s*indira\s+gandhi\s+national\s+open\s+university\s*$",
    r"(?i)^\s*ingou\s*$",                          # OCR variant of IGNOU
]

# ── Enhanced Option 2: Inline watermark strip patterns ───────────────────────
# These patterns match IGNOU watermark/logo text that bleeds INTO the middle
# of legitimate paragraph text (not as a standalone block). They are used by
# strip_inline_watermarks() to remove the contaminating phrase in-place.
_INLINE_WATERMARK_REGEXES = [
    re.compile(r"(?i)\s*ignou\s+the\s+people[''']?s\s+university\s*"),
    re.compile(r"(?i)\s*the\s+people[''']?s\s+university\s*"),
    re.compile(r"(?i)\s*he\s+people[''']?s\s+ople[''']?s\s*"),
    re.compile(r"(?i)\s*he\s+people[''']?s\s*"),
    re.compile(r"(?i)\s*people[''']?s\s+university\s*"),
    re.compile(r"(?i)\s*indira\s+gandhi\s+national\s+open\s+university\s*"),
    re.compile(r"(?i)\s*ignou\s*"),               # standalone IGNOU blob mid-sentence
]


# ── 2. COMPILED REGEXES ───────────────────────────────────────────────────────

COMPILED_HEADER       = [re.compile(p) for p in HEADER_PATTERNS]
COMPILED_FOOTER       = [re.compile(p) for p in FOOTER_PATTERNS]
COMPILED_COPYRIGHT    = [re.compile(p) for p in COPYRIGHT_PATTERNS]
COMPILED_TOC          = [re.compile(p) for p in TOC_PATTERNS]
COMPILED_WATERMARK    = [re.compile(p) for p in WATERMARK_PATTERNS]
COMPILED_BIBLIOGRAPHY = [re.compile(p) for p in BIBLIOGRAPHY_PATTERNS]
COMPILED_EXERCISE     = [re.compile(p) for p in EXERCISE_HEADING_PATTERNS]


# ── 3. DETECTOR CLASS ─────────────────────────────────────────────────────────

class BoilerplateDetector:
    """
    Detects boilerplate elements in structured document blocks.
    Can operate in single-pass mode or multi-page frequency analysis mode.
    """

    def __init__(self, page_height: float = 842.0):
        """
        Args:
            page_height: Typical A4 page height in points (842 pt = 297mm).
                         Used for margin-relative position checks.
        """
        self.page_height = page_height
        self._page_top_margin    = page_height * 0.08   # Top 8% of page
        self._page_bottom_margin = page_height * 0.92   # Bottom 8% of page

    def detect_block(self, block: Dict[str, Any], page_height: Optional[float] = None) -> Dict[str, Any]:
        """
        Examines a single block and adds boilerplate metadata fields:
          "is_boilerplate": bool
          "boilerplate_type": str | None

        Returns the modified block dict.
        """
        text = block.get("text", "").strip()
        if not text:
            block["is_boilerplate"] = False
            block["boilerplate_type"] = None
            return block

        # Use block bbox if available for position-based detection
        bbox = block.get("bbox")
        top_y = bbox[1] if (bbox and len(bbox) >= 4) else None
        bottom_y = bbox[3] if (bbox and len(bbox) >= 4) else None
        ph = page_height or self.page_height

        # ── Issue #9: Exercise headings — tag but do NOT mark as boilerplate ──
        for rx in COMPILED_EXERCISE:
            if rx.search(text):
                block["is_boilerplate"] = False
                block["boilerplate_type"] = "exercise_heading"
                block["type"] = "exercise_heading"
                return block

        # ── Issue #8: Bibliography entries — protect from copyright mis-classification ──
        if self._is_bibliography_entry(text):
            block["is_boilerplate"] = False
            block["boilerplate_type"] = "bibliography"
            return block

        b_type = self._check_text_and_position(text, top_y, bottom_y, ph)

        if b_type:
            block["is_boilerplate"] = True
            block["boilerplate_type"] = b_type
        else:
            block["is_boilerplate"] = False
            block["boilerplate_type"] = None

        return block

    def process_document(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Two-pass detection on full document block list:
          Pass 1: Pattern + position detection per block.
          Pass 2: Frequency analysis across pages (repeating lines on 3+ pages = header/footer).
          Pass 3: Issue #7 — Cross-reference header contamination cleanup.
          Pass 4: Issue #2 — ToC page number token reclassification.
        """
        # Pass 1: Pattern check
        for block in blocks:
            self.detect_block(block)

        # Pass 2: Repeating line detection (frequency analysis across pages)
        line_page_map: Dict[str, set] = {}
        for block in blocks:
            text = block.get("text", "").strip()
            page = block.get("page_num", 1)
            if text and len(text) < 120:         # Only track short-to-medium lines
                line_page_map.setdefault(text, set()).add(page)

        # Lines appearing identically on 3 or more distinct pages are likely boilerplate
        repeating_texts = {text for text, pages in line_page_map.items() if len(pages) >= 3}

        for block in blocks:
            # Don't override exercise_heading or bibliography classifications
            bp_type = block.get("boilerplate_type")
            if bp_type in ("exercise_heading", "bibliography"):
                continue
            if not block.get("is_boilerplate", False):
                text = block.get("text", "").strip()
                if text in repeating_texts:
                    block["is_boilerplate"] = True
                    block["boilerplate_type"] = "repeating_header_footer"

        # Pass 3: Normalize block["type"] for all boilerplate blocks
        for block in blocks:
            if block.get("is_boilerplate"):
                bp_type = block.get("boilerplate_type")
                if bp_type in ("header", "repeating_header_footer"):
                    block["type"] = "header"
                elif bp_type == "footer":
                    block["type"] = "footer"

        # Pass 3b: Issue F — Enforce is_boilerplate=True for blocks that Docling
        # labeled as type "footer" or "header" via its internal layout model but
        # that our pattern/position checks did NOT flag (is_boilerplate still False).
        # These blocks would bypass text_cleaner.py's boilerplate filter, causing
        # footer/header text to enter the RAG embedding pipeline.
        # Guard: skip exercise_heading and bibliography blocks which are
        # intentionally is_boilerplate=False despite their special type labels.
        _PROTECTED_BP_TYPES = {"exercise_heading", "bibliography"}
        for block in blocks:
            if block.get("boilerplate_type") in _PROTECTED_BP_TYPES:
                continue
            if not block.get("is_boilerplate", False):
                b_type = block.get("type", "")
                if b_type in ("footer", "header"):
                    # Only enforce if the text is short (< 120 chars) — real body
                    # paragraphs misclassified as header/footer by position are
                    # handled separately by block_cleaner Pass 7.
                    text = block.get("text", "").strip()
                    if len(text) < 120:
                        block["is_boilerplate"] = True
                        block["boilerplate_type"] = b_type
                        logger.debug(
                            f"Pass3b/FlagMismatch: '{text[:60]}' — "
                            f"type='{b_type}' was not boilerplate-flagged; corrected."
                        )

        # Pass 4: Issue #2 — Reclassify ToC page-number-only footer blocks on ToC pages
        blocks = self._reclassify_toc_page_numbers(blocks)

        # Pass 5 (Enhanced Option 2): Strip inline watermark bleed-through from
        # paragraph bodies. Full-block watermarks are caught above; this pass
        # handles the case where a watermark phrase is embedded mid-sentence.
        blocks = self._strip_inline_watermarks(blocks)

        return blocks

    # ── PRIVATE HELPERS ───────────────────────────────────────────────────────

    def _strip_inline_watermarks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enhanced Option 2 — Strip IGNOU watermark/logo text that bleeds into
        the interior of legitimate paragraph text blocks.

        Example:
          Before: "...due to the ignou THE PEOPLE'S UNIVERSITY growth of trade..."
          After:  "...due to the growth of trade..."

        Only non-boilerplate paragraph blocks are processed.
        """
        stripped_count = 0
        for block in blocks:
            if block.get("is_boilerplate", False):
                continue
            if block.get("type") not in ("paragraph", "heading", "list_item", "caption"):
                continue
            text = block.get("text", "")
            if not text:
                continue
            original = text
            for rx in _INLINE_WATERMARK_REGEXES:
                text = rx.sub(" ", text)
            # Collapse any double-spaces introduced by the removal
            text = re.sub(r"[ \t]{2,}", " ", text).strip()
            if text != original.strip():
                block["text"] = text
                block["was_corrected"] = True
                stripped_count += 1
                logger.debug(
                    f"InlineWatermarkStrip: Removed watermark bleed from "
                    f"block '{block.get('block_id')}' (page {block.get('page_num')})"
                )
        if stripped_count:
            logger.info(
                f"InlineWatermarkStrip: Stripped watermark bleed from {stripped_count} block(s)."
            )
        return blocks

    def _is_bibliography_entry(self, text: str) -> bool:
        """
        Issue #8: Returns True if the text looks like an academic bibliography entry.
        Such entries should NEVER be classified as 'copyright' boilerplate.
        """
        for rx in COMPILED_BIBLIOGRAPHY:
            if rx.search(text):
                return True
        return False

    def _reclassify_toc_page_numbers(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Issue #2: Detect Table of Contents pages and reclassify number-only footer blocks
        on those pages as "toc_page_number" instead of plain "footer".

        A ToC page is identified by having a large collapsed paragraph block whose text
        contains multiple theme/unit keywords (Course Contents, THEME, Unit).
        """
        # Identify pages that have a ToC-style content block
        toc_pages = set()
        toc_keywords = {"course contents", "theme", "unit", "introduction", "pages"}
        for block in blocks:
            text = block.get("text", "").lower()
            if block.get("type") == "paragraph" and len(text) > 200:
                kw_hits = sum(1 for kw in toc_keywords if kw in text)
                if kw_hits >= 3:
                    toc_pages.add(block.get("page_num"))

        if not toc_pages:
            return blocks

        for block in blocks:
            if block.get("page_num") in toc_pages:
                # Number-only blocks on ToC pages are ToC page numbers, not footers
                text = block.get("text", "").strip()
                if re.match(r"^\d{1,4}$", text) and block.get("is_boilerplate"):
                    block["boilerplate_type"] = "toc_page_number"
                    block["type"] = "toc_page_number"

        return blocks

    def _check_text_and_position(
        self,
        text: str,
        top_y: Optional[float],
        bottom_y: Optional[float],
        page_height: float
    ) -> Optional[str]:

        # 1. Check Page Number / Bare Footer
        for rx in COMPILED_FOOTER:
            if rx.search(text):
                return "footer"

        # 2. Check Header Patterns
        for rx in COMPILED_HEADER:
            if rx.search(text):
                return "header"

        # 3. Position-assisted Top Margin Header Check
        # In Docling's inverted coordinate system, HIGH Y = top of page.
        # A block is in the top margin when top_y > page_height * 0.93.
        if top_y is not None and top_y > (page_height * 0.93) and len(text) < 80:
            if any(word in text.lower() for word in ["upsc", "paper", "module", "chapter", "notes", "unit", "block"]):
                return "header"

        # 4. Position-assisted Bottom Margin Footer Check
        # LOW Y (near 0) = bottom of page in Docling coordinates.
        # A block is in the bottom margin when top_y < page_height * 0.07.
        if top_y is not None and top_y < (page_height * 0.07) and len(text) < 60:
            return "footer"

        # 5. Copyright / Contact info
        # Issue #8: Only match copyright patterns if the block does NOT look like a bibliography entry
        for rx in COMPILED_COPYRIGHT:
            if rx.search(text):
                return "copyright"

        # 6. Table of Contents line
        for rx in COMPILED_TOC:
            if rx.search(text):
                return "toc"

        # 7. Watermark
        for rx in COMPILED_WATERMARK:
            if rx.search(text):
                return "watermark"

        return None


# ── 4. CONVENIENCE FUNCTION ───────────────────────────────────────────────────

def tag_boilerplate_blocks(
    blocks: List[Dict[str, Any]],
    page_height: float = 842.0
) -> List[Dict[str, Any]]:
    """
    Tags all blocks in a document with 'is_boilerplate' and 'boilerplate_type'.

    Args:
        blocks: List of block dictionaries.
        page_height: Height of page in points (default: A4 = 842 pt).

    Returns:
        List of blocks with boilerplate metadata populated.
    """
    detector = BoilerplateDetector(page_height=page_height)
    return detector.process_document(blocks)
