import requests
import json

URL = "http://localhost:8000/api/v1/query"
PAYLOAD = {
    "query": "what is Australopithecus?",
    "top_k": 2
}

try:
    print(f"Sending POST request to {URL} ...")
    response = requests.post(URL, json=PAYLOAD)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("[SUCCESS] API responded successfully!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"[FAIL] Error response: {response.text}")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
