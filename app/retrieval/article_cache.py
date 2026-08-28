"""
app/retrieval/article_cache.py
───────────────────────────────
Cache layer for scraped web articles (used by the Current Affairs pipeline).

Prevents redundant network calls by caching article text keyed by URL.
Three backends are supported, selected via ARTICLE_CACHE_BACKEND in config:

    "memory"  — In-process LRU dict with a configurable max size.
                Zero dependencies. Cleared on process restart.

    "sqlite"  — Persistent SQLite table stored at ARTICLE_CACHE_SQLITE_PATH.
                Survives restarts. Entries expire after ARTICLE_CACHE_TTL_SECONDS.

    "redis"   — External Redis server (requires the `redis` package).
                Suitable for multi-process/multi-worker deployments.
                Falls back to memory if the `redis` package is not installed.

Public API:
    get_article(url: str) -> Optional[str]
        Return cached text for the URL, or None on a cache miss.

    store_article(url: str, content: str) -> None
        Persist article text to the configured backend.

    clear_cache() -> None
        Wipe all cached entries (useful for testing).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional

from app.core.config import (
    ARTICLE_CACHE_BACKEND,
    ARTICLE_CACHE_MAXSIZE,
    ARTICLE_CACHE_SQLITE_PATH,
    ARTICLE_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

# ── Memory Backend ─────────────────────────────────────────────────────────────

class _MemoryCache:
    """Thread-safe LRU cache backed by an OrderedDict."""

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, url: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(url)
            if entry is None:
                return None
            content, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[url]
                logger.debug(f"[Cache:memory] TTL expired for {url}")
                return None
            # Move to end (most recently used)
            self._store.move_to_end(url)
            logger.debug(f"[Cache:memory] HIT for {url}")
            return content

    def set(self, url: str, content: str) -> None:
        with self._lock:
            if url in self._store:
                self._store.move_to_end(url)
            self._store[url] = (content, time.time())
            if len(self._store) > self._maxsize:
                evicted = self._store.popitem(last=False)
                logger.debug(f"[Cache:memory] Evicted LRU entry: {evicted[0]}")

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ── SQLite Backend ─────────────────────────────────────────────────────────────

class _SQLiteCache:
    """Persistent cache stored in a local SQLite database."""

    _CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS article_cache (
        url       TEXT PRIMARY KEY,
        content   TEXT NOT NULL,
        stored_at REAL NOT NULL
    )
    """

    def __init__(self, db_path: str, ttl: int) -> None:
        self._db_path = db_path
        self._ttl = ttl
        self._lock = Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._conn()
            conn.execute(self._CREATE_TABLE)
            conn.commit()
            conn.close()

    def get(self, url: str) -> Optional[str]:
        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT content, stored_at FROM article_cache WHERE url = ?", (url,)
            ).fetchone()
            conn.close()
            if row is None:
                return None
            if time.time() - row["stored_at"] > self._ttl:
                self._delete(url)
                logger.debug(f"[Cache:sqlite] TTL expired for {url}")
                return None
            logger.debug(f"[Cache:sqlite] HIT for {url}")
            return row["content"]

    def set(self, url: str, content: str) -> None:
        with self._lock:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO article_cache (url, content, stored_at) VALUES (?, ?, ?)",
                (url, content, time.time()),
            )
            conn.commit()
            conn.close()

    def _delete(self, url: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM article_cache WHERE url = ?", (url,))
        conn.commit()
        conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = self._conn()
            conn.execute("DELETE FROM article_cache")
            conn.commit()
            conn.close()


# ── Redis Backend ──────────────────────────────────────────────────────────────

class _RedisCache:
    """Cache backed by Redis (SETEX / GET). Falls back to memory if redis-py is absent."""

    def __init__(self, ttl: int) -> None:
        self._ttl = ttl
        self._client = None
        try:
            import redis  # type: ignore
            self._client = redis.Redis(decode_responses=True)
            self._client.ping()
            logger.info("[Cache:redis] Redis backend connected.")
        except Exception as exc:
            logger.warning(
                f"[Cache:redis] Redis not available ({exc}). "
                "Falling back to in-memory cache."
            )
            self._fallback = _MemoryCache(
                maxsize=ARTICLE_CACHE_MAXSIZE, ttl=ttl
            )

    def get(self, url: str) -> Optional[str]:
        if self._client is None:
            return self._fallback.get(url)  # type: ignore[attr-defined]
        value = self._client.get(url)
        if value:
            logger.debug(f"[Cache:redis] HIT for {url}")
        return value  # type: ignore[return-value]

    def set(self, url: str, content: str) -> None:
        if self._client is None:
            self._fallback.set(url, content)  # type: ignore[attr-defined]
            return
        self._client.setex(url, self._ttl, content)

    def clear(self) -> None:
        if self._client is None:
            self._fallback.clear()  # type: ignore[attr-defined]
            return
        self._client.flushdb()


# ── Factory — select backend once at import time ───────────────────────────────

def _build_cache() -> _MemoryCache | _SQLiteCache | _RedisCache:
    backend = ARTICLE_CACHE_BACKEND.strip().lower()
    if backend == "sqlite":
        logger.info(f"[Cache] Using SQLite backend → {ARTICLE_CACHE_SQLITE_PATH}")
        return _SQLiteCache(
            db_path=ARTICLE_CACHE_SQLITE_PATH,
            ttl=ARTICLE_CACHE_TTL_SECONDS,
        )
    if backend == "redis":
        logger.info("[Cache] Using Redis backend.")
        return _RedisCache(ttl=ARTICLE_CACHE_TTL_SECONDS)
    # Default: memory
    logger.info(
        f"[Cache] Using in-memory LRU backend (maxsize={ARTICLE_CACHE_MAXSIZE}, "
        f"ttl={ARTICLE_CACHE_TTL_SECONDS}s)."
    )
    return _MemoryCache(
        maxsize=ARTICLE_CACHE_MAXSIZE,
        ttl=ARTICLE_CACHE_TTL_SECONDS,
    )


_cache = _build_cache()


# ── Public API ─────────────────────────────────────────────────────────────────

def get_article(url: str) -> Optional[str]:
    """
    Return cached article text for the given URL, or None on a cache miss.

    Args:
        url: The article URL used as the cache key.

    Returns:
        Cached text string, or None if not cached / TTL expired.
    """
    return _cache.get(url)


def store_article(url: str, content: str) -> None:
    """
    Persist scraped article text to the configured cache backend.

    Args:
        url:     The article URL (cache key).
        content: Full scraped article text.
    """
    _cache.set(url, content)


def clear_cache() -> None:
    """Wipe all cached entries. Primarily used in tests."""
    _cache.clear()
    logger.info("[Cache] All cached articles cleared.")
