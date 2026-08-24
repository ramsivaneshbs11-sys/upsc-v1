import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

raw_api_keys = os.environ.get("GEMINI_API_KEY", "").strip()
api_keys = [k.strip() for k in re.split(r"[,;]", raw_api_keys) if k.strip()]

# Test Key 4 (which is exhausted on gemini-3.7-flash with 20/day limit)
test_key = api_keys[3]
print(f"Testing Key 4: {test_key[:8]}...")
client = genai.Client(api_key=test_key)

lite_models = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite"
]

for model_name in lite_models:
    print(f"\nTesting {model_name}...")
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=["Hello"]
        )
        print(f"  Result: SUCCESS! Response: {resp.text.strip()}")
    except Exception as e:
        print(f"  Result: FAILED! Error: {e}")
