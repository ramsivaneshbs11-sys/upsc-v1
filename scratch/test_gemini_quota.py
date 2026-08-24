import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

raw_api_keys = os.environ.get("GEMINI_API_KEY", "").strip()

if not raw_api_keys:
    print("Error: GEMINI_API_KEY environment variable is not set!")
    sys.exit(1)

# Split keys like in production code
api_keys = [k.strip() for k in re.split(r"[,;]", raw_api_keys) if k.strip()]
print(f"Total API Keys loaded from .env: {len(api_keys)}")

from google import genai

# Test each key individually
for idx, key in enumerate(api_keys, start=1):
    masked = f"{key[:8]}...{key[-8:] if len(key) > 8 else '***'}"
    print(f"\n[{idx}/{len(api_keys)}] Testing Key: {masked}")
    
    try:
        client = genai.Client(api_key=key)
        # Use the same model as production (gemini_client.py GEMINI_MODEL = "gemini-flash-latest")
        resp = client.models.generate_content(
            model="gemini-flash-latest",
            contents=["Hello, say 'Key works'"]
        )
        print(f"  Result: Success! Response: {resp.text.strip()}")
    except Exception as e:
        print(f"  Result: FAILED!")
        print(f"  Error details: {e}")
