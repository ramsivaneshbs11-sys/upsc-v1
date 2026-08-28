"""
scratch/verify_netting_fix.py
End-to-end verification for the Netting fix.
Usage: python scratch/verify_netting_fix.py
Requires: uvicorn app.main:app --reload --port 8000
"""
import sys, os, json, time
from pathlib import Path

# Fix Windows terminal Unicode (special dashes, arrows, etc.)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

TEST_QUERY = "About Netting robert mcC"
API_URL    = "http://localhost:8000/api/v1/query"
MODE       = "mains"
SEP        = "=" * 65


def banner(t):
    print(f"\n{SEP}\n  {t}\n{SEP}")


# TEST 1: Groq Classifier
def test_classifier():
    banner("TEST 1 - Groq Classifier")
    print(f"  Query   : {TEST_QUERY!r}")
    print("  Expected: Anthropology with confidence >= 0.85")
    try:
        from app.retrieval.query_classifier import classify_query
        result = classify_query(TEST_QUERY)
        cls    = result["classification"]
        conf   = result["confidence"]
        print(f"  Result     : {cls}")
        print(f"  Confidence : {conf:.3f}")
        if cls == "Anthropology" and conf >= 0.85:
            print("  [PASS] Correctly classified as Anthropology")
            return True
        else:
            print(f"  [FAIL] Got {cls!r} ({conf:.3f}) -- expected Anthropology >= 0.85")
            return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


# TEST 2: Live API Query
def test_live_query():
    banner("TEST 2 - Live API Query")
    print(f"  Endpoint: {API_URL}")
    print(f"  Query   : {TEST_QUERY!r}")
    print(f"  Mode    : {MODE}")
    try:
        import requests
        payload = {"query": TEST_QUERY, "mode": MODE, "session_id": None}
        t0      = time.time()
        resp    = requests.post(API_URL, json=payload, timeout=60)
        elapsed = time.time() - t0
        if resp.status_code != 200:
            print(f"  [FAIL] API status {resp.status_code}")
            print(f"  Body : {resp.text[:300]}")
            return False
        data      = resp.json()
        answer    = data.get("answer", "")
        answered  = data.get("answered", False)
        citations = data.get("citations", [])
        route     = data.get("route", "unknown")
        cache_hit = data.get("cache_hit", False)
        print(f"  Route    : {route}")
        print(f"  Answered : {answered}")
        print(f"  CacheHit : {cache_hit}")
        print(f"  Time     : {elapsed:.2f}s")
        print(f"  Citations: {citations}")
        print("\n  -- Full Answer --")
        for line in answer.split("\n"):
            print("  " + line)
        chicago = "chicago" in answer.lower()
        checks = [
            ("answered=true",            answered is True),
            ("has citations",            len(citations) > 0),
            ("mentions Netting",         "netting" in answer.lower()),
            ("mentions anthropology",    "anthropolog" in answer.lower()),
            ("has GS paper tag",         "gs paper" in answer.lower() or "relevant for" in answer.lower()),
            ("University of Chicago *",  chicago),
        ]
        print("\n  -- Quality Checks --")
        print("  (* requires PDF re-ingestion to pass)")
        all_ok = True
        for name, passed in checks:
            icon = "[PASS]" if passed else "[FAIL]"
            if not passed and "*" not in name:
                all_ok = False
            print(f"  {icon}  {name}")
        if not chicago:
            print("  [INFO] University of Chicago missing -- re-ingest PDFs to fix.")
        return all_ok
    except Exception as e:
        if "Connection" in type(e).__name__ or "connection" in str(e).lower():
            print("  [FAIL] Cannot connect to the server.")
            print("  [INFO] Run: uvicorn app.main:app --reload --port 8000")
        else:
            print(f"  [FAIL] {type(e).__name__}: {e}")
        return False


def main():
    banner("UPSC RAG -- Netting Fix Verification")
    print(f"  Query: {TEST_QUERY!r}")

    t1 = test_classifier()
    t2 = test_live_query()

    banner("FINAL RESULT")
    for name, passed in [("Classifier case-insensitive fix", t1),
                         ("Live API answer quality",          t2)]:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}]  {name}")
    print()
    if t1 and t2:
        print("  ALL TESTS PASSED -- Netting fix is working correctly!")
    else:
        print("  SOME TESTS FAILED -- check output above.")
    print()


if __name__ == "__main__":
    main()
