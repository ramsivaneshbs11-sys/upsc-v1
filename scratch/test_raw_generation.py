import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from google import genai
from extraction.gemini_client import render_page_to_jpeg, GEMINI_MODEL

def main():
    pdf_path = ROOT_DIR / "[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf"
    page_num = 54
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    image_bytes = render_page_to_jpeg(pdf_path, page_num)
    
    print("Sending request to Gemini...")
    from google.genai import types as genai_types
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            "Extract all text from this page."
        ]
    )
    
    print("\n--- FULL RESPONSE OBJECT ---")
    print(response)
    print("----------------------------\n")

if __name__ == "__main__":
    main()
