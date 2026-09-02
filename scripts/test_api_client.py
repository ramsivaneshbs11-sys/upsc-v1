import sys
import requests
from pathlib import Path

# API Server URL
API_URL = "http://localhost:8000/api/v1/documents"


def test_upload():
    # Find any PDF in inputs/ or use a fallback path
    workspace_dir = Path(__file__).resolve().parent
    pdf_files = list(workspace_dir.rglob("*.pdf"))

    if not pdf_files:
        print("[ERROR] No PDF files found in the workspace inputs directory to test with.")
        print("Please place a test PDF in inputs/ or provide a path to a PDF.")
        sys.exit(1)

    test_pdf = pdf_files[0]
    print(f"[INFO] Found test PDF: {test_pdf}")

    # Set classification to History or Anthropology
    classification = "History"

    print(f"[INFO] Sending POST request to {API_URL} ...")
    with open(test_pdf, "rb") as f:
        files = {"file": (test_pdf.name, f, "application/pdf")}
        data = {"classification": classification}
        try:
            response = requests.post(API_URL, files=files, data=data)
            print(f"[INFO] Status Code: {response.status_code}")
            if response.status_code in [200, 201]:
                print("[SUCCESS] API responded successfully!")
                import json
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"[FAIL] Error response: {response.text}")
        except Exception as e:
            print(f"[ERROR] Failed to connect to server: {e}")
            print("Make sure you started the FastAPI server with:")
            print("  python -m uvicorn app.main:app --reload")


if __name__ == "__main__":
    test_upload()
