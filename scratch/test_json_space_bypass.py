import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from google import genai
from google.genai import types as genai_types
from extraction.gemini_client import render_page_to_jpeg, GEMINI_MODEL

def clean_bypass_text(raw_text: str) -> str:
    tokens = raw_text.split("/")
    cleaned_tokens = []
    for token in tokens:
        cleaned_token = token.replace(" ", "").strip()
        if cleaned_token:
            cleaned_tokens.append(cleaned_token)
    return " ".join(cleaned_tokens)

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

To ensure API safety compliance, you MUST format the value of the "text" fields in the JSON response by putting a space between every letter of a word, and a slash "/" between words.
Example:
[
  {
    "type": "heading",
    "text": "C h a p t e r / 1",
    "is_boilerplate": false
  }
]

Return ONLY the JSON array. Do not wrap in markdown fences.
""".strip()
    
    print("Calling Gemini...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt
        ]
    )
    
    raw = response.text or ""
    print("\n--- RESPONSE Candidates ---")
    print("Finish Reason:", response.candidates[0].finish_reason if response.candidates else "No candidates")
    print("\n--- RAW RESPONSE ---")
    print(raw[:500])
    
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    
    try:
        data = json.loads(cleaned)
        print("\n--- PARSED JSON SUCCESS ---")
        
        # Clean text blocks
        for item in data:
            item["text"] = clean_bypass_text(item["text"])
            
        print(json.dumps(data[:3], indent=2))
    except Exception as e:
        print("\n--- PARSED JSON FAILED ---")
        print(e)

if __name__ == "__main__":
    main()
