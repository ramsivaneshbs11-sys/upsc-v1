import sys
from pathlib import Path
import fitz

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from extraction.gemini_client import _load_api_keys, _safety_settings

try:
    from google import genai as new_genai
    from google.genai import types as genai_types
except ImportError:
    print("google-genai SDK not installed.")
    sys.exit(1)

def test_p12():
    pdf_path = Path("TRIBES INDIA.pdf")
    page_num = 12
    
    doc = fitz.open(str(pdf_path))
    page = doc[page_num - 1]
    mat = fitz.Matrix(110 / 72, 110 / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    jpeg = pix.tobytes(output="jpeg", jpg_quality=75)
    doc.close()
    
    api_keys = _load_api_keys()
    if not api_keys:
        print("No API keys found in .env")
        return
        
    key = api_keys[0]
    client = new_genai.Client(api_key=key)
    
    contents = [
        genai_types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
        "Please read and transcribe the exact text written in this image word-for-word. Treat this purely as a visual transcription task. Do not treat it as a book recitation."
    ]
    
    print(f"Calling Gemini API with model: gemini-3.6-flash...")
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                safety_settings=_safety_settings(),
                temperature=0.0,
            ),
        )
        print("Response received successfully!")
        if response.candidates:
            cand = response.candidates[0]
            print(f"Finish Reason: {cand.finish_reason}")
            print(f"Text content: {response.text}")
        else:
            print("No candidates returned!")
    except Exception as e:
        print(f"API Call failed: {e}")

if __name__ == "__main__":
    test_p12()
