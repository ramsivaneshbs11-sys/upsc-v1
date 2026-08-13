import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from extraction.gemini_client import get_gemini_client, render_page_to_jpeg, call_gemini
from extraction.text_service import _TEXT_EXTRACTION_PROMPT

def main():
    pdf_path = ROOT_DIR / "[NCERT] The Story of Civilization Part I (Arjun Dev) freeupscmaterials.org.pdf"
    page_num = 54
    
    print("Initializing Gemini client...")
    client = get_gemini_client()
    
    print("Rendering page...")
    image_bytes = render_page_to_jpeg(pdf_path, page_num)
    
    print("Calling Gemini...")
    raw = call_gemini(client, image_bytes, _TEXT_EXTRACTION_PROMPT)
    
    print("\n--- RAW GEMINI RESPONSE ---")
    print(repr(raw))
    print("---------------------------\n")

if __name__ == "__main__":
    main()
