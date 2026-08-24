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

# Test Key 4
test_key = api_keys[3]
print(f"Testing Key 4: {test_key[:8]}...")
client = genai.Client(api_key=test_key)

models_to_test = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest"
]

for model_name in models_to_test:
    print(f"\n--- Testing model: {model_name} ---")
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=["Hello, say 'Key works'"]
        )
        print(f"  Result: SUCCESS! Response: {resp.text.strip()}")
    except Exception as e:
        print(f"  Result: FAILED! Error: {e}")
