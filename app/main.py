"""
app/main.py
────────────
FastAPI application entry point.

Start server:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Interactive docs:
    http://localhost:8000/docs
"""
import logging
import sys
from pathlib import Path

# ── Ensure workspace root is on sys.path ───────────────────────────────────
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent  # daily/
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

# Disable HuggingFace symlinks on Windows (required for Docling models)
import os
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

from app.database.session import engine, Base
from app.api.routes import documents
from app.api.routes import extract_page as extract_page_v2
from app.api.routes import query as query_route
from app.services.qdrant_service import ensure_collections


# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: create tables + Qdrant collections on startup ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables if needed …")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready ✓")

    logger.info("Verifying Qdrant collections …")
    ensure_collections()

    yield
    logger.info("Shutting down …")



# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="UPSC RAG — Document Ingestion & Retrieval API",
    description=(
        "## Ingestion Endpoints\n\n"
        "### v1 — Docling Extractor (digital PDFs)\n"
        "- `POST /api/v1/documents` — Upload **one or more** PDF files\n"
        "- `POST /api/v1/documents/folder` — Ingest all PDFs from a **server-side folder path**\n\n"
        "### v2 — Gemini 2.5 Flash Extractor (all PDFs)\n"
        "- `POST /api/v2/documents` — Upload **one or more** PDF files\n"
        "- `POST /api/v2/documents/folder` — Ingest all PDFs from a **server-side folder path**\n\n"
        "**Pipeline per file:** Validate → Save → Register (PostgreSQL) → Extract → "
        "Preprocess + Chunk → Embed (BGE) → Qdrant upsert\n\n"
        "---\n\n"
        "## Retrieval Endpoint\n\n"
        "- `POST /api/v1/query` — Intelligent retrieval layer\n\n"
        "**Pipeline:** Classify (Gemini Flash) → Route (High/Medium/Low confidence) → "
        "Vector Search (Qdrant) or Web Search (DuckDuckGo) → Rerank (MiniLM) → Top-K chunks"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── Dynamic OpenAPI Fix for Swagger UI File Uploads ──────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Recursively find application/octet-stream properties and change to format: binary
    def fix_binary_format(d):
        if isinstance(d, dict):
            if d.get("contentMediaType") == "application/octet-stream":
                d["format"] = "binary"
                del d["contentMediaType"]
            for v in d.values():
                fix_binary_format(v)
        elif isinstance(d, list):
            for v in d:
                fix_binary_format(v)

    fix_binary_format(openapi_schema)
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ── Routers ───────────────────────────────────────────────────────────────
# Ingestion
app.include_router(documents.router)
app.include_router(extract_page_v2.router)
# Retrieval
app.include_router(query_route.router)


# ── Health check ──────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
