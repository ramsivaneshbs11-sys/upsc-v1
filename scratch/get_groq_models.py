import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r"c:\Users\vishn\Downloads\RAG-main\RAG-main\.env"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}"
}

try:
    resp = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        models = [m["id"] for m in resp.json().get("data", [])]
        print("Available Groq Models:")
        for m in sorted(models):
            print(f"  - {m}")
    else:
        print(resp.text)
except Exception as e:
    print(f"Error: {e}")
