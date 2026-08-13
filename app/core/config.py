import os
from pathlib import Path
from dotenv import load_dotenv

# ── Root of the daily/ workspace ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # daily/

# Load environment variables from the .env file
load_dotenv(BASE_DIR / ".env")

# ── PostgreSQL connection ──────────────────────────────────────────────────
# Set this as an environment variable or create a .env file.
# Format: postgresql://<user>:<password>@<host>:<port>/<dbname>
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/upsc_rag",
)

# ── File storage directories ───────────────────────────────────────────────
UPLOAD_DIR: Path = BASE_DIR / "uploads"
EXTRACTED_DIR: Path = BASE_DIR / "data" / "extracted"
PREPROCESSED_DIR: Path = BASE_DIR / "data" / "preprocessed"

# Allowed document classifications
ALLOWED_CLASSIFICATIONS = ["History", "Anthropology"]

# ── Qdrant vector database ─────────────────────────────────────────────────
QDRANT_HOST: str = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.environ.get("QDRANT_PORT", "6333"))

# One Qdrant collection per classification (lowercase)
QDRANT_COLLECTION_MAP: dict[str, str] = {
    "History": "history_collection",
    "Anthropology": "anthropology_collection",
}

# ── Embedding model ────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME: str = os.environ.get(
    "EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5"
)
EMBEDDING_DIMENSION: int = 768  # Output dimension of BAAI/bge-base-en-v1.5

# ── Gemini 2.5 Flash (Endpoint 2) ────────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL:   str = "gemini-3.5-flash"

# Ensure directories exist on startup
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "history").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "anthropology").mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
