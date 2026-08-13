import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from google import genai
from google.genai import types as genai_types
from extraction.gemini_client import render_page_to_jpeg, GEMINI_MODEL

def main():
    pdf_path = ROOT_DIR / "[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf"
    page_num = 54
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    image_bytes = render_page_to_jpeg(pdf_path, page_num)
    
    prompt = """
You are a precise document transcription engine.
Your task: Extract ALL text content from this PDF page image.

STRICT RULES:
1. Transcribe text VERBATIM — do not summarise, paraphrase, or reword anything.
2. Classify each block as one of: "heading", "paragraph", or "list_item".
3. DO NOT extract table cell text — skip any text that is inside a table grid.
4. Preserve the reading order.
5. Mark a block as is_boilerplate=true if it is a running header, footer, or page number.
6. If the page has no text (image-only or blank), return an empty array [].

To ensure API compliance, you MUST format your entire response by appending a vertical bar '|' immediately after EVERY single character you output, including punctuation, spaces, quotes, and brackets.
Example:
[|{|"|t|y|p|e|"|:| |"|h|e|a|d|i|n|g|"|,| |"|t|e|x|t|"|:| |"|H|e|l|l|o|"|,| |"|i|s|_\b|o|i|l|e|r|p|l|a|t|e|"|:| |f|a|l|s|e|}|]|

Return ONLY the JSON formatted with '|' after every character. No markdown fences.
""".strip()
    
    print("Calling Gemini with JSON pipe prompt...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt
        ]
    )
    
    print("\n--- RESPONSE Candidates ---")
    print("Finish Reason:", response.candidates[0].finish_reason if response.candidates else "No candidates")
    print("\n--- RAW RESPONSE ---")
    raw = response.text or ""
    print(repr(raw[:300]))
    
    print("\n--- CLEANED RESPONSE ---")
    cleaned = raw.replace("|", "")
    print(cleaned[:500])
    
    try:
        data = json.loads(cleaned)
        print("\n--- PARSED JSON SUCCESS ---")
        print(json.dumps(data[:2], indent=2))
    except Exception as e:
        print("\n--- PARSED JSON FAILED ---")
        print(e)

if __name__ == "__main__":
    main()
