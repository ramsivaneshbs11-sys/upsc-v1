import os
import re
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\.env"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
api_keys = [k.strip() for k in re.split(r"[,;]", GEMINI_API_KEY) if k.strip()]

print(f"Total keys found in .env: {len(api_keys)}")

for idx, key in enumerate(api_keys):
    masked = f"{key[:8]}..." if len(key) > 8 else "***"
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-3.5-flash")
        response = model.generate_content("Hello, reply with one word.")
        print(f"Key {idx} ({masked}): SUCCESS -> {response.text.strip()}")
    except Exception as e:
        print(f"Key {idx} ({masked}): FAILED -> {e}")
