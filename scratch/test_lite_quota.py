import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from google import genai

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Try gemini-3.5-flash-lite
    print("Testing gemini-3.5-flash-lite...")
    try:
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=["Hello, say testing 123"]
        )
        print("Success:", resp.text.strip())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
