import sys
import logging
from pathlib import Path

# Add workspace root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.embedding_service import run_embedding

json_path = ROOT_DIR / "data" / "preprocessed" / "11e56f0d-36f1-4efb-893d-54e24888b158_preprocessed.json"
print(f"Checking if file exists: {json_path.exists()}")

print("Running embedding service on the file...")
success, embedded_chunks, error_message = run_embedding(json_path)

print(f"Success: {success}")
print(f"Error Message: {error_message}")
if embedded_chunks:
    print(f"Number of embedded chunks: {len(embedded_chunks)}")
