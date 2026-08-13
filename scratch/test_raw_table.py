import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("test_raw_table")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from google import genai
from google.genai import types as genai_types
from extraction.gemini_client import get_gemini_client, render_page_to_jpeg, call_gemini

def clean_bypass_text(raw_text: str) -> str:
    tokens = raw_text.split("/")
    cleaned_tokens = []
    for token in tokens:
        cleaned_token = token.replace(" ", "").strip()
        if cleaned_token:
            cleaned_tokens.append(cleaned_token)
    return " ".join(cleaned_tokens)

def main():
    pdf_path = ROOT_DIR / "uploads" / "anthropology" / "01bded9f-4da3-427c-9111-3acd4a37f858.pdf"
    page_num = 18
    
    logger.info("Initializing Gemini client...")
    client = get_gemini_client(0)
    image_bytes = render_page_to_jpeg(pdf_path, page_num)
    
    prompt = """
You are a precise document table extraction engine.

Your task: Extract ALL tables from this PDF page image.

STRICT RULES:
1. Identify every table present on the page (there may be 0, 1, or more).
2. For each table:
   - Extract the header row as a list of column name strings.
   - Extract all data rows — each row is a list of cell value strings.
   - Transcribe cell values VERBATIM. Do not paraphrase or abbreviate.
   - If a caption or title is present above/below the table, extract it.
3. DO NOT extract any non-table text.
4. If the page has NO tables, return [].

To ensure API compliance, you MUST format every cell value string (including headers, caption, and row cells) by putting a space between every letter of a word, and a slash "/" between words.
Example:
"P h y l e t i c / G r a d u a l i s m"

Return ONLY a JSON array with this exact structure — no markdown fences, no extra keys:
[
  {
    "caption": "T a b l e / 2 / c a p t i o n",
    "headers": ["F e a t u r e", "P h y l e t i c / G r a d u a l i s m", "P u n c t u a t e d / E q u i l i b r i u m"],
    "rows": [
      ["1 . / R a t e / o f / c h a n g e", "U n i f o r m l y / l o w", "H i g h"]
    ]
  }
]
""".strip()

    logger.info("Sending request with space/slash bypass prompt...")
    response_text = call_gemini(client, image_bytes, prompt)
    
    print("\n--- RAW RESPONSE ---")
    print(response_text)
    print("--------------------\n")
    
    if response_text:
        import json
        try:
            # clean code fences if present
            cleaned_json = response_text.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.split("\n", 1)[1]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json.rsplit("\n", 1)[0]
            
            data = json.loads(cleaned_json)
            for tbl in data:
                tbl["caption"] = clean_bypass_text(tbl.get("caption", ""))
                tbl["headers"] = [clean_bypass_text(h) for h in tbl.get("headers", [])]
                tbl["rows"] = [[clean_bypass_text(cell) for cell in row] for row in tbl.get("rows", [])]
            print("\n--- CLEANED PARSED JSON ---")
            print(json.dumps(data, indent=2))
        except Exception as e:
            print("Failed to parse cleaned JSON:", e)

if __name__ == "__main__":
    main()
