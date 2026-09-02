"""
app/api/routes/admin.py
───────────────────────
Admin endpoints for cache inspection and management.

Endpoints:
    GET    /api/v1/admin/cache/stats         → Response cache + article cache stats
    DELETE /api/v1/admin/cache/response      → Clear the SQLite response cache
    DELETE /api/v1/admin/cache/articles      → Clear the in-memory/SQLite article cache
    DELETE /api/v1/admin/cache/all           → Clear both caches at once
    GET    /api/v1/admin/storage/stats       → Qdrant collections + DB storage overview
"""
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin — Cache & Storage"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _file_size_mb(path: str | Path | None) -> float | None:
    """Return file size in MB, or None if the file doesn't exist."""
    try:
        if path and Path(path).exists():
            return round(Path(path).stat().st_size / (1024 * 1024), 3)
    except Exception:
        pass
    return None


def _response_cache_stats() -> dict[str, Any]:
    """Pull live stats from the SQLite response cache."""
    try:
        from app.retrieval.response_cache import cache_stats, _db_path
        stats = cache_stats()
        stats["db_size_mb"] = _file_size_mb(_db_path)
        return stats
    except Exception as exc:
        return {"error": str(exc), "enabled": False}


def _article_cache_stats() -> dict[str, Any]:
    """Best-effort stats for the article cache (memory / SQLite / Redis)."""
    try:
        from app.retrieval.article_cache import _cache, ARTICLE_CACHE_BACKEND
        from app.core.config import ARTICLE_CACHE_BACKEND as backend_name, ARTICLE_CACHE_SQLITE_PATH

        result: dict[str, Any] = {"backend": backend_name}

        if backend_name == "memory":
            # _MemoryCache exposes ._store
            store = getattr(_cache, "_store", {})
            now = time.time()
            ttl = getattr(_cache, "_ttl", 0)
            live = sum(1 for _, (_, ts) in store.items() if now - ts <= ttl)
            result.update({
                "total_entries": len(store),
                "live_entries":  live,
                "maxsize":       getattr(_cache, "_maxsize", None),
                "ttl_seconds":   ttl,
            })
        elif backend_name == "sqlite":
            import sqlite3
            try:
                conn = sqlite3.connect(ARTICLE_CACHE_SQLITE_PATH)
                total = conn.execute("SELECT COUNT(*) FROM article_cache").fetchone()[0]
                conn.close()
                result.update({
                    "total_entries": total,
                    "db_size_mb":    _file_size_mb(ARTICLE_CACHE_SQLITE_PATH),
                })
            except Exception as e:
                result["error"] = str(e)
        elif backend_name == "redis":
            client = getattr(_cache, "_client", None)
            if client:
                result["redis_connected"] = True
                result["redis_dbsize"]    = client.dbsize()
            else:
                result["redis_connected"] = False

        return result
    except Exception as exc:
        return {"error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/cache/stats",
    summary="Get cache stats (response cache + article cache)",
)
def get_cache_stats():
    """
    Returns detailed stats for both cache layers:
    - **Response Cache**: SQLite-backed cache of full RAG answers.
    - **Article Cache**: Web article scrape cache (memory / SQLite / Redis).
    """
    return {
        "response_cache": _response_cache_stats(),
        "article_cache":  _article_cache_stats(),
        "timestamp":      time.time(),
    }


@router.delete(
    "/cache/response",
    summary="Clear the RAG response cache",
)
def clear_response_cache():
    """
    Deletes all entries from the SQLite response cache.
    The next query for any previously-cached question will re-run the full RAG pipeline.
    """
    try:
        from app.retrieval.response_cache import clear_cache
        deleted = clear_cache()
        logger.info(f"[Admin] Response cache cleared — {deleted} entries deleted.")
        return {
            "status":  "cleared",
            "deleted": deleted,
            "message": f"Response cache cleared: {deleted} entries removed.",
        }
    except Exception as exc:
        logger.exception(f"[Admin] Failed to clear response cache: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/cache/articles",
    summary="Clear the web article scrape cache",
)
def clear_article_cache():
    """
    Wipes all cached web article content from the article cache.
    The next Current Affairs query will re-scrape fresh content.
    """
    try:
        from app.retrieval.article_cache import clear_cache as clear_articles
        clear_articles()
        logger.info("[Admin] Article cache cleared.")
        return {
            "status":  "cleared",
            "message": "Article cache cleared.",
        }
    except Exception as exc:
        logger.exception(f"[Admin] Failed to clear article cache: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/cache/all",
    summary="Clear ALL caches (response + articles)",
)
def clear_all_caches():
    """
    Clears both the response cache and the article scrape cache in one call.
    """
    errors = []
    response_deleted = 0

    try:
        from app.retrieval.response_cache import clear_cache
        response_deleted = clear_cache()
    except Exception as exc:
        errors.append(f"Response cache: {exc}")

    try:
        from app.retrieval.article_cache import clear_cache as clear_articles
        clear_articles()
    except Exception as exc:
        errors.append(f"Article cache: {exc}")

    logger.info(f"[Admin] All caches cleared. Response entries deleted: {response_deleted}")
    return {
        "status":                  "cleared" if not errors else "partial",
        "response_entries_deleted": response_deleted,
        "errors":                  errors,
        "message":                 (
            f"All caches cleared. {response_deleted} response entries removed."
            if not errors else
            f"Partial clear. Errors: {'; '.join(errors)}"
        ),
    }


@router.get(
    "/storage/stats",
    summary="Get storage overview (Qdrant + DB)",
)
def get_storage_stats():
    """
    Returns a high-level storage overview:
    - Qdrant: number of collections and total vectors per collection.
    - PostgreSQL: registered document count.
    - SQLite caches: file sizes.
    """
    result: dict[str, Any] = {}

    # ── Qdrant collections ───────────────────────────────────────────────────
    try:
        from qdrant_client import QdrantClient
        from app.core.config import QDRANT_HOST, QDRANT_PORT
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=5)
        collections = client.get_collections().collections
        result["qdrant"] = {
            "status":      "connected",
            "collections": [
                {
                    "name":         col.name,
                    "vectors_count": (
                        getattr(client.get_collection(col.name), "points_count", None)
                        or getattr(client.get_collection(col.name), "vectors_count", 0)
                        or 0
                    ),
                }
                for col in collections
            ],
            "total_collections": len(collections),
        }
    except Exception as exc:
        result["qdrant"] = {"status": "error", "error": str(exc)}

    # ── PostgreSQL documents ─────────────────────────────────────────────────
    try:
        from app.database.session import engine
        import sqlalchemy as sa
        with engine.connect() as conn:
            count = conn.execute(sa.text("SELECT COUNT(*) FROM documents")).scalar()
        result["postgresql"] = {
            "status":           "connected",
            "documents_indexed": count,
        }
    except Exception as exc:
        result["postgresql"] = {"status": "error", "error": str(exc)}

    # ── SQLite cache file sizes ──────────────────────────────────────────────
    try:
        from app.core.config import RESPONSE_CACHE_SQLITE_PATH, ARTICLE_CACHE_SQLITE_PATH, ARTICLE_CACHE_BACKEND
        result["sqlite_files"] = {
            "response_cache_mb": _file_size_mb(RESPONSE_CACHE_SQLITE_PATH),
            "article_cache_mb":  (
                _file_size_mb(ARTICLE_CACHE_SQLITE_PATH)
                if ARTICLE_CACHE_BACKEND == "sqlite" else None
            ),
        }
    except Exception as exc:
        result["sqlite_files"] = {"error": str(exc)}

    result["timestamp"] = time.time()
    return result
