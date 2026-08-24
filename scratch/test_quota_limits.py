import os
import sys
import re
import time
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

print("\nRunning a rapid test of 25 calls on gemini-flash-latest to see if the quota is > 20 per day...")
success_count = 0
for i in range(1, 30):
    try:
        resp = client.models.generate_content(
            model="gemini-flash-latest",
            contents=["Hello"]
        )
        success_count += 1
        print(f"Call {i}: SUCCESS")
        time.sleep(0.5) # small delay to avoid RPM limit (typically 15 RPM or similar)
    except Exception as e:
        print(f"Call {i}: FAILED - {e}")
        break

print(f"\nCompleted! Total successful calls: {success_count}")
