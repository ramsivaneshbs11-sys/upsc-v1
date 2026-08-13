"""
Test: diagram extraction additions to text_service.py
Run from project root: python scratch/test_diagram_extraction.py
"""
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from extraction.text_service import clean_bypass_text, _split_diagram_text, _parse_text_response

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def test(name, condition, detail=""):
    if condition:
        print(f"  {PASS}: {name}")
    else:
        print(f"  {FAIL}: {name} — {detail}")

print("=" * 60)
print("  text_service diagram extraction — unit tests")
print("=" * 60)

# ── Test 1: clean_bypass_text still works for normal text ──────────
result = clean_bypass_text("C h a p t e r / 1")
test("clean_bypass_text: normal text", result == "Chapter 1", f"got: {result!r}")

# ── Test 2: _split_diagram_text with explicit ---SUMMARY--- ────────
diagram_text = (
    "```mermaid\n"
    "graph TD\n"
    '    A["Start"] --> B{"Check"}\n'
    '    B -->|Yes| C["End"]\n'
    "```\n"
    "---SUMMARY---\n"
    "Start, check condition, then End."
)
code, summary = _split_diagram_text(diagram_text)
test("_split_diagram_text: mermaid block extracted", "```mermaid" in code, f"code={code[:40]!r}")
test("_split_diagram_text: summary extracted", "Start, check" in summary, f"summary={summary!r}")

# ── Test 3: _split_diagram_text — graceful fallback (no separator) ─
diagram_no_sep = (
    "```mermaid\n"
    "graph TD\n"
    '    A["Start"] --> B["End"]\n'
    "```\n"
    "This shows Start to End."
)
code2, summary2 = _split_diagram_text(diagram_no_sep)
test("_split_diagram_text: fallback without separator", "```mermaid" in code2, f"code2={code2[:40]!r}")
test("_split_diagram_text: fallback summary non-empty", len(summary2) > 0, f"summary2={summary2!r}")

# ── Test 4: _parse_text_response — diagram block preserved ─────────
raw_blocks = [
    {
        "type": "diagram",
        "text": (
            "```mermaid\n"
            "graph TD\n"
            '    A["Upload"] --> B["Process"]\n'
            "```\n"
            "---SUMMARY---\n"
            "Upload then process."
        ),
        "is_boilerplate": False
    },
    {
        "type": "paragraph",
        "text": "H e l l o / W o r l d",
        "is_boilerplate": False
    }
]
blocks = _parse_text_response(json.dumps(raw_blocks), page_number=1)
test("_parse_text_response: returns 2 blocks", blocks is not None and len(blocks) == 2,
     f"got: {blocks}")
if blocks:
    test("_parse_text_response: diagram type preserved", blocks[0]["type"] == "diagram")
    test("_parse_text_response: mermaid not corrupted", "```mermaid" in blocks[0]["text"])
    test("_parse_text_response: paragraph bypass-cleaned", blocks[1]["text"] == "Hello World",
         f"got: {blocks[1]['text']!r}")

# ── Test 5: Fake diagram (no Mermaid) falls back to paragraph ──────
fake_diagram = [
    {"type": "diagram", "text": "T h i s / i s / n o t / a / d i a g r a m", "is_boilerplate": False}
]
fallback_blocks = _parse_text_response(json.dumps(fake_diagram), page_number=2)
test("_parse_text_response: fake diagram reclassified to paragraph",
     fallback_blocks is not None and fallback_blocks[0]["type"] == "paragraph",
     f"got: {fallback_blocks}")

print()
print("All tests complete.")
