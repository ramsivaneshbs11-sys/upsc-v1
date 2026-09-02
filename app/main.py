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

from fastapi import FastAPI, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database.session import engine, Base
from app.database import classification_models  # noqa: F401 — registers Classification table with Base
from app.api.routes import documents
from app.api.routes import extract_page as extract_page_v2
from app.api.routes import query as query_route
from app.api.routes import classifications as classification_route  # dynamic classification management
from app.api.routes import query_stream as query_stream_route       # SSE streaming endpoint
from app.api.routes import news as news_route                       # Daily news endpoints
from app.api.routes import mcq as mcq_route                         # MCQ practice endpoints
from app.api.routes import admin as admin_route                     # Admin cache & storage endpoints
from app.services.qdrant_service import ensure_collections
from app.core.config import (
    RESPONSE_CACHE_ENABLED,
    RESPONSE_CACHE_TTL_SECONDS,
    RESPONSE_CACHE_MAXSIZE,
    RESPONSE_CACHE_SQLITE_PATH,
)


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

    # ── Pre-load the reranker model so first user request has no cold-start ──
    logger.info("Pre-loading cross-encoder reranker model …")
    from app.retrieval.reranker import preload_reranker
    preload_reranker()

    # ── Pre-load the BGE embedding model so first search request has no cold-start ──
    logger.info("Pre-loading BGE embedding model …")
    from app.services.embedding_service import _get_model as preload_embedding
    preload_embedding()

    # ── Initialise response cache ─────────────────────────────────────────
    from app.retrieval.response_cache import init_cache as init_response_cache
    init_response_cache(
        db_path     = RESPONSE_CACHE_SQLITE_PATH,
        ttl_seconds = RESPONSE_CACHE_TTL_SECONDS,
        max_entries = RESPONSE_CACHE_MAXSIZE,
        enabled     = RESPONSE_CACHE_ENABLED,
    )
    logger.info(
        f"Response cache ready ✔ "
        f"(enabled={RESPONSE_CACHE_ENABLED}, ttl={RESPONSE_CACHE_TTL_SECONDS}s)"
    )

    # ── Start Daily News Scraper Scheduler (06:00 AM) ─────────────────────
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.services.news_scraper_service import run_daily_news_scraper
    from app.core.config import NEWS_SCRAPER_CRON_HOUR, NEWS_SCRAPER_CRON_MINUTE

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_news_scraper,
        "cron",
        hour=NEWS_SCRAPER_CRON_HOUR,
        minute=NEWS_SCRAPER_CRON_MINUTE,
        id="daily_news_scraper",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Daily news scraper scheduled at {NEWS_SCRAPER_CRON_HOUR:02d}:{NEWS_SCRAPER_CRON_MINUTE:02d} daily ✓"
    )

    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
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

# ── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve UI & Favicon ───────────────────────────────────────────────────────
@app.get("/", response_class=FileResponse, tags=["UI"])
def read_root():
    """Serves the upsc_ui.html frontend interface."""
    return FileResponse(_WORKSPACE_ROOT / "upsc_ui.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Handles browser favicon requests with 204 No Content to prevent 404 logs."""
    return Response(status_code=204)

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
app.include_router(query_stream_route.router)   # SSE streaming variant
# Classification Management
app.include_router(classification_route.router)
# Daily News & MCQ (merged from ram_chatbot-main)
app.include_router(news_route.router)
app.include_router(mcq_route.router)
# Admin — Cache & Storage Management
app.include_router(admin_route.router)


# ── Health check ──────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
