import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\.env"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

models_to_test = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "allam-2-7b"
]

for model in models_to_test:
    print(f"\nTesting model: {model}")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Respond with ONLY a JSON object: {\"status\": \"ok\"}"}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10.0
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Response: {resp.json()['choices'][0]['message']['content'].strip()}")
        else:
            print(f"  Error: {resp.text}")
    except Exception as e:
        print(f"  Request failed: {e}")
