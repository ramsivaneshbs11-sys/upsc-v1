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

# Test Key 4 (which failed with 404)
test_key = api_keys[3] # Index 3 is 4th key
print(f"Testing Key 4: {test_key[:8]}...")

client = genai.Client(api_key=test_key)
try:
    models = client.models.list()
    print("Available models:")
    for m in models:
        print(f" - {m.name} (displayName: {m.display_name})")
except Exception as e:
    print(f"Error listing models: {e}")
