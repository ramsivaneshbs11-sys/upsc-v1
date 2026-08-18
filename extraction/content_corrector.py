"""
content_corrector.py
──────────────────────
Fixes common OCR/Docling extraction errors in UPSC study material text.

Corrections applied:
  1. Hyphenated word break joining across line breaks ("gov- \n ernment" -> "government")
  2. OCR artifact replacements (ligatures, odd unicode quotes/dashes)
  3. UPSC domain term normalization ("U.P.S.C." -> "UPSC", "I.A.S." -> "IAS")
  4. De-duplication of accidental repeated words ("the the" -> "the")
  5. Whitespace normalization (collapsing multiple spaces/newlines)
  6. URL whitespace normalization (spaces inside URL paths removed)         [Issue #11]
  7. Fused-word OCR split fix (e.g. "monotheistsant" -> "monotheist saint") [Issue #5]
  8. Split-word OCR join fix (e.g. "V ol." -> "Vol.", "Y ork" -> "York")    [Issue #12]
  9. Running-header tail stripping from paragraph ends                       [Issue #6]

Output field added/updated in block dicts:
  "text": corrected text string
  "was_corrected": bool
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger("content_corrector")

# ── 1. DOMAIN REPLACEMENTS MAP ────────────────────────────────────────────────

DOMAIN_TERM_MAP = {
    r"\bU\.P\.S\.C\.\b": "UPSC",
    r"\bI\.A\.S\.\b": "IAS",
    r"\bI\.P\.S\.\b": "IPS",
    r"\bI\.F\.S\.\b": "IFS",
    r"\bC\.S\.A\.T\.\b": "CSAT",
    r"\bN\.C\.E\.R\.T\.\b": "NCERT",
    r"\bM\.L\.A\.\b": "MLA",
    r"\bM\.P\.\b": "MP",
    r"\bB\.C\.E\.\b": "BCE",
    r"\bC\.E\.\b": "CE",
}

# OCR Character & PUA Glyph fixes
CHAR_REPLACEMENTS = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2014": "-",
    "\u2013": "-",
    "\u2026": "...",
    "\xa0": " ",       # Non-breaking space
    "\u200b": "",      # Zero-width space
    "\ufb01": "fi",         # Ligature fi
    "\ufb02": "fl",         # Ligature fl
    "\ufb00": "ff",         # Ligature ff
    "\ufb03": "ffi",        # Ligature ffi
    # Spurious diacritics / OCR glyph corruption
    "\u00cd": "I",
    "\u00ed": "i",
    "\u0146": "n",
    # PUA Symbol / Wingdings Font Glyph Mappings (Issue 4 fix)
    "\uf050": "✓",
    "\uf051": "✓",
    "\uf052": "✓",
    "\uf078": "✗",
    "\uf0a7": "•",
    "\uf0b7": "•",
    "\uf0d8": "➢",
    "\uf0e0": "✉",
    "\uf020": " ",
    "\ufffd": "•",
}

# OCR Confusion Pair Replacements
OCR_CONFUSION_MAP = {
    r"\bThls\b": "This",
    r"\bthls\b": "this",
    r"\bsublecl\b": "subject",
    r"\bcondillon\b": "condition",
    r"\bcondillons\b": "conditions",
    r"\bthal\b": "that",
    r"\bil\b": "it",
    r"\bnol\b": "not",
    r"\{ho\b": "the",
    r"\blo\b": "to",
    r"\bwhlch\b": "which",
    r"\bwilh\b": "with",
    r"\bElforn\b": "Ellora",
    r"\bTempte\b": "Temple",
    # ── Issue 6: OCR/character fixes for reported extraction issues ─────────────
    r"\baud\b": "and",
    r"\bAud\b": "And",
    r"\bThiugs\b": "Things",
    r"\bthiugs\b": "things",
    r"\bPreachiug\b": "Preaching",
    r"\bpreachiug\b": "preaching",
    r"\bfiņd\b": "find",
    r"\bTne\b": "The",
    r"\bI'he\b": "The",
    r"\beaste['']?n\b": "eastern",
    r"\brnle\b": "rule",
    r"\bFhe\b": "The",
    r"\bgrealust\b": "greatest",
    r"\bsurious\b": "serious",
    r"\bsurhus\b": "serious",
    r"\bmeanirig\b": "meaning",
    r"\bterins\b": "terms",
    r"\bSyslem\b": "System",
    r"\bfoumndations\b": "foundations",
    r"\bfoumndatios\b": "foundations",
    r"\bHinduslan\b": "Hindustan",
    r"\bHíndu\b": "Hindu",
    r"\bÍndia\b": "India",
    r"\bgrulling\b": "gruelling",
    r"\bGrulling\b": "Gruelling",
    r"\bplebianize\b": "plebeianize",
    r"\bPlebianize\b": "Plebeianize",
    r"\bKesselschlact\b": "Kesselschlacht",
    r"\bkesselschlact\b": "kesselschlacht",
    r"\bSull[- ]k[iu]tl?\b": "Sulh-kul",
    r"\bentrused\b": "entrusted",
    r"\breligon\b": "religion",
    r"\bunifed\b": "unified",
    r"\bcial\b": "social",
    r"SOCIAL SCIENCE PART 1 SOCIAL SCIENCE - PART 1": "SOCIAL SCIENCE - PART I",
    r"SOCIAL SCIENCE - PART 1 SOCIAL SCIENCE - PART 1": "SOCIAL SCIENCE - PART I",
    # ── Issue #5: Fused OCR word fixes ──────────────────────────────────────────
    # "monotheistsant" is an OCR fusion of "monotheist saint"
    r"\bmonotheistsant\b": "monotheist saint",
    r"\bMonotheistsant\b": "Monotheist Saint",
    # Other common word fusions observed in IGNOU booklets
    r"\bSikhismsant\b": "Sikhism saint",
    r"\bHindusiant\b": "Hindu saint",
    r"\bBhaktisant\b": "Bhakti saint",
    r"\bgurubhakti\b": "guru bhakti",
    r"\bGurubhakti\b": "Guru Bhakti",
    r"\bRajputstate\b": "Rajput state",
    r"\brajputstate\b": "Rajput state",
    r"\bMughalcourt\b": "Mughal court",
    r"\bmughalcourt\b": "Mughal court",
    r"\bMughalempire\b": "Mughal Empire",
    r"\bmughalempire\b": "Mughal Empire",
    r"\bSubahdar\b": "Subahdar",
    # ── Issue C: IGNOU Anthropology / BANC-107 OCR confusion pairs ─────────
    # Residual OCR errors observed in Docling output for IGNOU courseware.
    # Character substitution pattern: 'c' → 'e', 'rn' → 'm', dropped chars.
    r"\bInbrceding\b": "Inbreeding",
    r"\binbrceding\b": "inbreeding",
    r"\bMeasurcments\b": "Measurements",
    r"\bmeasurcments\b": "measurements",
    r"\bCollcction\b": "Collection",
    r"\bcollcction\b": "collection",
    r"\bComposd\b": "Composed",
    r"\bPrintcd\b": "Printed",
    r"\bGrcatcr\b": "Greater",
    r"\bgrcatcr\b": "greater",
    r"\bDclhi\b": "Delhi",
    r"\bPhasc-Il\b": "Phase-II",
    r"\bPhasc\b": "Phase",
    r"\bLathccf\b": "Latheef",
    r"\blathccf\b": "latheef",
    r"\bshas\s+defined\b": "has defined",
    r"\bdealswith\b": "deals with",
    r"\bDealswith\b": "Deals with",
    r"\bNew\s+Dehi\b": "New Delhi",
    r"\bnew\s+dehi\b": "new delhi",
    # ── Enhanced Option 2: Extended IGNOU Anthropology (BANC-107/108) OCR pairs ──
    # Additional character-substitution errors observed in anthropology courseware.
    r"\bHominids\b": "Hominids",
    r"\bhominds\b": "hominids",
    r"\bpopulatoin\b": "population",
    r"\bPopulatoin\b": "Population",
    r"\bvariaiton\b": "variation",
    r"\bVariaiton\b": "Variation",
    r"\bvariaitons\b": "variations",
    r"\bVariaitons\b": "Variations",
    r"\banthroplogical\b": "anthropological",
    r"\bAnthroplogical\b": "Anthropological",
    r"\banthroplogist\b": "anthropologist",
    r"\bAnthroplogist\b": "Anthropologist",
    r"\banthroplogists\b": "anthropologists",
    r"\bAnthroplogists\b": "Anthropologists",
    r"\banthroplogic\b": "anthropologic",
    r"\bphysicai\b": "physical",
    r"\bPhysicai\b": "Physical",
    r"\bbiologicai\b": "biological",
    r"\bBiologicai\b": "Biological",
    r"\bcuitural\b": "cultural",
    r"\bCuitural\b": "Cultural",
    r"\bsoicety\b": "society",
    r"\bSoicety\b": "Society",
    r"\bsoicetal\b": "societal",
    r"\bSoicetal\b": "Societal",
    r"\bkinshp\b": "kinship",
    r"\bKinshp\b": "Kinship",
    r"\bmarraiage\b": "marriage",
    r"\bMarraiage\b": "Marriage",
    r"\bmarraiages\b": "marriages",
    r"\bdescnt\b": "descent",
    r"\bDescnt\b": "Descent",
    r"\blineaage\b": "lineage",
    r"\bLineaage\b": "Lineage",
    r"\blineaages\b": "lineages",
    r"\btribal\s+socites\b": "tribal societies",
    r"\bTribal\s+Socites\b": "Tribal Societies",
    r"\bethnicty\b": "ethnicity",
    r"\bEthnicty\b": "Ethnicity",
    r"\bethnogarphy\b": "ethnography",
    r"\bEthnogarphy\b": "Ethnography",
    r"\bethnogarphic\b": "ethnographic",
    r"\banthropoogy\b": "anthropology",
    r"\bAnthropoogy\b": "Anthropology",
    r"\bsocio-cultual\b": "socio-cultural",
    r"\bSocio-Cultual\b": "Socio-Cultural",
    r"\bsociocultual\b": "sociocultural",
    r"\bpastoralsim\b": "pastoralism",
    r"\bPastoralsim\b": "Pastoralism",
    r"\bnomadsim\b": "nomadism",
    r"\bNomadsim\b": "Nomadism",
    r"\bpeasnatry\b": "peasantry",
    r"\bPeasnatry\b": "Peasantry",
    r"\bfunctionailsm\b": "functionalism",
    r"\bFunctionailsm\b": "Functionalism",
    r"\bstructurailsm\b": "structuralism",
    r"\bStructurailsm\b": "Structuralism",
    r"\bsymobl\b": "symbol",
    r"\bSymobl\b": "Symbol",
    r"\bsymobls\b": "symbols",
    r"\brituai\b": "ritual",
    r"\bRituai\b": "Ritual",
    r"\brituais\b": "rituals",
    r"\bsymbosim\b": "symbolism",
    r"\bSymbosim\b": "Symbolism",
    r"\btotemisn\b": "totemism",
    r"\bTotemisn\b": "Totemism",
    r"\banimisn\b": "animism",
    r"\bAnimisn\b": "Animism",
}

# ── Issue #12: Split-word OCR join patterns ────────────────────────────────────
# These are pairs where OCR inserted a space inside a single word.
# Applied as regex substitutions with word boundaries to avoid false positives.
SPLIT_WORD_FIXES = [
    # "V ol." → "Vol.", "V olume" → "Volume"
    (re.compile(r"\bV\s+ol\."), "Vol."),
    (re.compile(r"\bV\s+olume\b"), "Volume"),
    # "Y ork" → "York"
    (re.compile(r"\bY\s+ork\b"), "York"),
    # "V ernacular" → "Vernacular"
    (re.compile(r"\bV\s+ernacular"), "Vernacular"),
    # "MiddleEastern" → "Middle Eastern" (missing space between words)
    (re.compile(r"\bMiddleEastern\b"), "Middle Eastern"),
    (re.compile(r"\bmiddleeastern\b", re.IGNORECASE), "Middle Eastern"),
    # "CentralAsian" → "Central Asian"
    (re.compile(r"\bCentralAsian\b"), "Central Asian"),
    # "SouthAsian" → "South Asian"
    (re.compile(r"\bSouthAsian\b"), "South Asian"),
    # "NorthIndia" → "North India" (when not a known compound proper noun)
    (re.compile(r"\bNorthIndia\b"), "North India"),
    (re.compile(r"\bSouthIndia\b"), "South India"),
    # "S hah" → "Shah", "K han" → "Khan" (OCR space splits in names)
    (re.compile(r"\bS\s+hah\b"), "Shah"),
    (re.compile(r"\bK\s+han\b"), "Khan"),
    (re.compile(r"\bK\s+hafi\b"), "Khafi"),
    # "ImreBangha" → "Imre Bangha" (joined author names in bibliography)
    (re.compile(r"\bImreBangha\b"), "Imre Bangha"),
    # "Perso-Islamic" — keep hyphen; fix if split
    (re.compile(r"\bPerso\s+-\s+Islamic\b"), "Perso-Islamic"),
    # "Sabk-i Hindi" — keep as-is; fix broken variants
    (re.compile(r"\bSabk\s+-\s+i\s+Hindi\b"), "Sabk-i Hindi"),
    # "Rekhta" variants
    (re.compile(r"\bNagari\s+Rekhta\b"), "Nagari Rekhta"),
    # "ChandarBhan" → "Chandar Bhan"
    (re.compile(r"\bChandarBhan\b"), "Chandar Bhan"),
    # Generic: "Andhara" → "Andhra" (common OCR variant)
    (re.compile(r"\bAndhara\s+Pradesh\b"), "Andhra Pradesh"),
]

# ── Issue #6: Running-header strings that may be contaminating paragraph ends ──
# These are exact phrases used as running chapter headers in IGNOU booklets.
# If a paragraph block ends with one of these phrases, the trailing phrase is stripped.
RUNNING_HEADER_PHRASES = [
    "Persian Histories and Memoirs",
    "Sources and Literary Traditions",
    "History of India-VII",
    "History of India-VI",
    "History of Modern Europe",
    "History of China",
    "Political Processes",
    "Production and Commercial Practices",
    "State, Society and Religion",
    "Visual Culture",
    "Society and Culture",
    "The 18th Century",
    "Mughal Decline and Disintegration",
    "Sanskrit Kavya Literature, Regional Sources and Travelogues",
    "Indian Ocean Trade Network",
    "Trading Communities and Commercial Practices",
    "Religious Ideas and Movements",
    "Courtly Culture",
    "Women and Gender",
    # ── Issue H: IGNOU Anthropology (BANC-107) chapter running headers ───────
    # These chapter titles appear as running headers on the right-hand page margin
    # and bleed into paragraph tail text when extracted by Docling.
    "Importance and Implications of Biological Variation",
    "Introduction to Biological Diversity",
    "Sources of Genetic Variation",
    "Genetic Polymorphism",
    "Role of Bio-cultural Factors",
    "Ethnic Elements in Indian Population",
    "Classification of Racial Elements in India",
    "Major Races of Mankind",
    "Demographic Anthropology",
    "Indian Demography",
    "Inbreeding and Consanguinity",
    "Biological Diversity in Human Populations",
]

# Build regex for trailing running-header detection at paragraph end.
# Matches the header phrase possibly preceded by a space, at string end.
_HEADER_TAIL_PATTERNS = [
    re.compile(r"\s*" + re.escape(phrase) + r"\s*$")
    for phrase in RUNNING_HEADER_PHRASES
]

# ── Issue C: Citation page-range de-garbler ────────────────────────────────
# OCR of academic citation page ranges sometimes produces a duplicated leading
# digit prefix, e.g. "pp. 4452-471" instead of "pp. 452-471".
# Pattern: pp. followed by a number where the first 1-2 digits are duplicated.
_CITATION_PAGERANGE_RE = re.compile(
    r"(pp?\.\s*)(\d)(\d{2,3})(-\d{2,4})"
)

def _fix_citation_page_ranges(text: str) -> str:
    """
    Issue C: Fixes garbled academic citation page ranges.
    Example: 'pp. 4452-471' -> 'pp. 452-471'
             'p. 1123-34'   -> 'p. 123-34'
    """
    def _fix_range(m: re.Match) -> str:
        prefix  = m.group(1)   # "pp. "
        dup     = m.group(2)   # leading duplicated digit
        rest    = m.group(3)   # remaining digits
        end     = m.group(4)   # "-471"
        correct_start = rest   # drop the duplicated leading digit
        return f"{prefix}{correct_start}{end}"

    return _CITATION_PAGERANGE_RE.sub(_fix_range, text)

# ── Issue #11: URL whitespace normalization ────────────────────────────────────
# Removes stray spaces inside URL segments (common in scanned PDFs where
# the space-bar key width causes splits inside path tokens).
_URL_SPACE_REGEX = re.compile(
    r"(https?://\S*?)\s+(\S*(?:\.[a-zA-Z]{2,}|/)\S*)"
)

def _normalize_url_spaces(text: str) -> str:
    """Collapse whitespace injected inside URL paths by the scanner."""
    # Iteratively collapse spaces inside URL-like sequences
    # Pattern: http://... <space> path_fragment
    prev = None
    while prev != text:
        prev = text
        text = _URL_SPACE_REGEX.sub(r"\1\2", text)
    return text


# ── Issue #6: Strip running-header suffix from paragraph text ─────────────────

def _strip_running_header_tail(text: str) -> str:
    """
    If the paragraph text ends with a known running-header phrase
    (e.g. '...due to the Persian Histories and Memoirs'),
    strip that trailing header phrase.
    """
    for pattern in _HEADER_TAIL_PATTERNS:
        stripped = pattern.sub("", text)
        if stripped != text:
            logger.debug(f"Stripped running-header tail from paragraph: ...{text[-60:]!r}")
            return stripped.rstrip()
    return text


# ── Issue #6b: Strip running-header injected mid-paragraph ────────────────────
# Handles cases where the header text is injected mid-sentence rather than just at the end.
def _strip_running_header_inline(text: str) -> str:
    """
    If a known running-header phrase appears inline within paragraph text
    (inserted by OCR between two words of the same sentence), remove it.
    """
    for phrase in RUNNING_HEADER_PHRASES:
        # Match the phrase when it appears sandwiched between word characters
        # e.g. "Nainsi ri Khyat Sources and Literary Traditions and Marwar"
        # We look for the phrase surrounded by spaces (not at start/end)
        pattern = re.compile(r"(?<=\w)\s+" + re.escape(phrase) + r"\s+(?=\w)")
        match = pattern.search(text)
        if match:
            # Replace the injected header phrase (with surrounding spaces) with a single space
            text = text[:match.start()] + " " + text[match.end():]
            logger.debug(f"Stripped inline running-header: {phrase!r}")
    return text


# ── Foreign/technical terms italic emphasis ────────────────────────────────────
# Issue 6 fix (original): Foreign/technical terms that should be emphasised with markdown *italics*
FOREIGN_TERMS_TO_EMPHASIZE = [
    "schwerpunkt",
    "auftragstaktik",
    "blitzkrieg",
    "levee en masse",
    "volk",
    "volksgemeinschaft",
    "jihad",
    "jehad",
    "ghazi",
    "Kesselschlacht",
    "kesselschlacht",
]

# Compiled regex patterns for foreign-term emphasis (whole-word, case-sensitive)
_FOREIGN_TERM_REGEXES = [
    (re.compile(r"(?<![*])\b(" + re.escape(term) + r")\b(?![*])"), r"*\1*")
    for term in FOREIGN_TERMS_TO_EMPHASIZE
]

COMPILED_DOMAIN_TERMS = [(re.compile(pattern), repl) for pattern, repl in DOMAIN_TERM_MAP.items()]
COMPILED_OCR_TERMS = [(re.compile(pattern), repl) for pattern, repl in OCR_CONFUSION_MAP.items()]
HYPHEN_LINEBREAK_REGEX = re.compile(r"(\b[a-zA-Z]{2,})-\s*\n\s*([a-zA-Z]{2,}\b)")
REPEATED_WORD_REGEX   = re.compile(r"\b([a-zA-Z]{3,})\s+\1\b", re.IGNORECASE)
MULTIPLE_SPACES_REGEX = re.compile(r"[ \t]{2,}")
MULTIPLE_NEWLINES_REGEX = re.compile(r"\n{3,}")

# ── Enhanced Option 2: List-marker normalizer ─────────────────────────────────
# IGNOU booklets use diverse bullet characters: arrows (➢ • > - – *) and
# inconsistent numeral formats ("1)" vs "1." vs "(1)"). Normalise them so
# that chunkers / embedders see consistent list syntax.
_BULLET_NORMALIZER = re.compile(
    r"^[ \t]*(?:[\u2022\u2023\u25e6\u2043\u25aa\u25ab\u25cf\u25cb\u2019\u27a2\u25b8\u25b9\u25ba\u25bb\u2794\u2192>\*]|\-{1,2}|\u2013|\u2014)[ \t]+",
    re.MULTILINE,
)
_NUMERAL_NORMALIZER = re.compile(
    r"^[ \t]*(\d{1,2})[\.\)\]:][ \t]+",
    re.MULTILINE,
)


def _normalize_list_markers(text: str) -> str:
    """
    Enhanced Option 2 — Normalize diverse bullet and numeral list markers.

    Converts all arrow/dash/star bullets to '• ' and normalises numeral
    formats ("1)" / "(1)" / "1.") to "1. ".
    """
    text = _BULLET_NORMALIZER.sub("• ", text)
    text = _NUMERAL_NORMALIZER.sub(lambda m: f"{m.group(1)}. ", text)
    return text



# ── 2. CONTENT CORRECTOR CLASS ────────────────────────────────────────────────

class ContentCorrector:
    """
    Applies text cleaning and normalization rules to raw extracted text.
    """

    def correct_text(self, text: str) -> tuple[str, bool]:
        """
        Corrects raw text string.

        Returns:
            (corrected_text: str, was_changed: bool)
        """
        if not text:
            return "", False

        original = text
        corrected = original

        # Rule 1: Character & Ligature Replacement
        for char, repl in CHAR_REPLACEMENTS.items():
            if char in corrected:
                corrected = corrected.replace(char, repl)

        # Rule 2: Join Hyphenated Words across line breaks ("gov-\nernment" -> "government")
        corrected = HYPHEN_LINEBREAK_REGEX.sub(r"\1\2", corrected)

        # Rule 3: UPSC Domain Abbreviation Normalization ("U.P.S.C." -> "UPSC")
        for regex, replacement in COMPILED_DOMAIN_TERMS:
            corrected = regex.sub(replacement, corrected)

        # Rule 4: OCR Character Swap & Confusion Repair (includes fused-word fixes Issue #5)
        for regex, replacement in COMPILED_OCR_TERMS:
            corrected = regex.sub(replacement, corrected)

        # Rule 4b: Issue #12 — Split-word OCR joins ("V ol." -> "Vol.", "MiddleEastern" -> "Middle Eastern")
        for pattern, replacement in SPLIT_WORD_FIXES:
            corrected = pattern.sub(replacement, corrected)

        # Rule 4c (Enhanced Option 2): Normalise list-bullet markers
        # (➢, –, *, - etc.) to canonical • and numeral formats to "N. ".
        corrected = _normalize_list_markers(corrected)

        # Rule 5: Remove accidental duplicate words ("the the" -> "the")
        corrected = REPEATED_WORD_REGEX.sub(r"\1", corrected)

        # Rule 6: Rejoin mangled transliteration diacritics ("Hir ṇ ayak ṣ a" -> "Hiraṇyakaṣa")
        corrected = re.sub(r"(\w)\s+([ṇṣśñṭḍṛḷṃḥĀāĪīŪūṚṛṜṝḶḷḸḹṂṃḤḥÑñṬṭḌḍṆṇŚśṢṣ])\s*(\w)", r"\1\2\3", corrected)
        corrected = re.sub(r"(\w)\s+([ṇṣśñṭḍṛḷṃḥĀāĪīŪūṚṛṜṝḶḷḸḹṂṃḤḥÑñṬṭḌḍṆṇŚśṢṣ])", r"\1\2", corrected)

        # Rule 7: Whitespace Normalization
        corrected = MULTIPLE_SPACES_REGEX.sub(" ", corrected)
        corrected = MULTIPLE_NEWLINES_REGEX.sub("\n\n", corrected)

        # Rule 8: Issue #11 — URL whitespace normalization
        corrected = _normalize_url_spaces(corrected)

        # Rule 8b: Issue C — Citation page-range de-garbler ("pp. 4452-471" -> "pp. 452-471")
        corrected = _fix_citation_page_ranges(corrected)

        # Rule 9: Issue #6 — Strip running-header contamination (tail & inline)
        corrected = _strip_running_header_tail(corrected)
        corrected = _strip_running_header_inline(corrected)

        # Rule 10: Issue 6 (original) — Emphasis/italic wrapping for foreign/technical terms
        for regex, repl in _FOREIGN_TERM_REGEXES:
            corrected = regex.sub(repl, corrected)

        corrected = corrected.strip()
        was_changed = (corrected != original.strip())

        return corrected, was_changed

    def correct_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies text corrections to a block dict in-place.
        Adds metadata fields:
          "was_corrected": bool
          "raw_text": str (saved if corrections were made)
        """
        raw = block.get("text", "")
        corrected, changed = self.correct_text(raw)

        if changed:
            block["raw_text"] = raw
            block["text"] = corrected
            block["was_corrected"] = True
        else:
            block["was_corrected"] = False

        return block

    def correct_document(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Applies text corrections across all blocks in a document list.
        """
        corrected_count = 0
        for block in blocks:
            self.correct_block(block)
            if block.get("was_corrected"):
                corrected_count += 1

        logger.info(f"ContentCorrector: Corrected {corrected_count}/{len(blocks)} blocks")
        return blocks


# ── 3. CONVENIENCE FUNCTIONS ───────────────────────────────────────────────────

# Regex to detect whether a string ends with a sentence-terminal character.
_TERMINAL_RE = re.compile(r"[.!?:\u2019\"'\u201d]\s*$")
# Regex to detect whether a string starts with an uppercase letter (new sentence).
_STARTS_UPPER_RE = re.compile(r"^[A-Z\u2018\u201c]")


def merge_cross_page_sentences(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Issue 4 — Merge sentences that were split across page boundaries.

    When a paragraph block ends without terminal punctuation (no period / colon /
    question mark / exclamation) AND the very next non-boilerplate paragraph on
    the following page starts with a lowercase letter (i.e. is a continuation),
    the two blocks are merged into one.

    Only paragraph/body types are merged.  Heading and list_item blocks are
    never merged with adjacent blocks.
    """
    MERGEABLE_TYPES = {"paragraph"}
    merged: List[Dict[str, Any]] = []
    i = 0
    merge_count = 0

    while i < len(blocks):
        current = blocks[i]
        cur_type = current.get("type", "")
        cur_text = current.get("text", "").rstrip()
        cur_page = current.get("page_num", 0)

        if (
            cur_type in MERGEABLE_TYPES
            and not current.get("is_boilerplate", False)
            and cur_text
            and not _TERMINAL_RE.search(cur_text)
        ):
            # Look ahead: find the next non-boilerplate block
            j = i + 1
            while j < len(blocks) and blocks[j].get("is_boilerplate", False):
                j += 1

            if j < len(blocks):
                nxt = blocks[j]
                nxt_type = nxt.get("type", "")
                nxt_text = nxt.get("text", "").lstrip()
                nxt_page = nxt.get("page_num", 0)

                # Merge only if:
                # (a) next block is a paragraph on the NEXT page, and
                # (b) it continues with a lowercase letter (mid-sentence)
                if (
                    nxt_type in MERGEABLE_TYPES
                    and nxt_page == cur_page + 1
                    and nxt_text
                    and not _STARTS_UPPER_RE.match(nxt_text)
                ):
                    # Merge: join text, keep current block's metadata
                    current = dict(current)   # shallow copy so we don't mutate original
                    current["text"] = cur_text + " " + nxt_text
                    current["was_corrected"] = True
                    # Skip the consumed next block
                    blocks = blocks[:j] + blocks[j+1:]
                    merge_count += 1
                    logger.debug(
                        f"Merged cross-page sentence: page {cur_page} -> {nxt_page}, "
                        f"'{cur_text[-40:]}'... + '{nxt_text[:40]}...'"
                    )

        merged.append(current)
        i += 1

    if merge_count:
        logger.info(f"CrossPageMerger: merged {merge_count} split sentence(s) across page breaks")

    return merged


def correct_extracted_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience wrapper to apply content corrections to a list of block dicts.
    Applies:
      1. Per-block text corrections (OCR fixes, ligatures, emphasis, whitespace).
      2. Cross-page sentence merging (Issue 4).
    """
    corrector = ContentCorrector()
    blocks = corrector.correct_document(blocks)
    blocks = merge_cross_page_sentences(blocks)
    return blocks
