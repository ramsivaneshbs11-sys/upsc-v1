import requests
import json

try:
    r = requests.get("http://localhost:8000/openapi.json")
    if r.status_code == 200:
        schema = r.json()
        body_schema = schema.get("components", {}).get("schemas", {}).get("Body_ingest_files_gemini_api_v2_documents_post", {})
        print("=== Multipart Body Schema ===")
        print(json.dumps(body_schema, indent=2))
    else:
        print(f"Failed to fetch openapi.json. Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
