import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env
load_dotenv(Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\.env"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": GROQ_MODEL,
    "messages": [
        {"role": "user", "content": "Respond with a JSON object containing a key 'hello' and value 'world'."}
    ],
    "temperature": 0.0,
    "response_format": {"type": "json_object"}
}

try:
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=15.0
    )
    print(f"Status: {resp.status_code}")
    print(resp.text)
except Exception as e:
    print(f"Error: {e}")
