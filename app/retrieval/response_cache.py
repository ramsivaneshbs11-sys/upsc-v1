"""
app/retrieval/response_cache.py
────────────────────────────────
SQLite-backed Response Cache for the RAG pipeline.

Caches complete QueryResponse payloads keyed by a hash of
(normalised_query + "|" + mode) so identical questions skip
Qdrant, the reranker, and the LLM entirely on subsequent requests.

Design:
  - Backend   : stdlib sqlite3 — zero extra dependencies.
  - Key       : sha256(strip(lower(query)) + "|" + mode)
  - TTL       : configurable (default 7 days). Expired rows auto-evicted on read.
  - Max size  : configurable (default 1000 rows). Oldest entries pruned on insert.
  - Thread-safe: WAL journal mode + per-call connection (no shared state).
  - Modes     : only "prelims" and "mains" are cacheable.
                "current_affairs" is always excluded (live web search).

Public API:
    get_response(query, mode)            -> dict | None
    set_response(query, mode, payload)   -> None
    clear_cache()                        -> int   (rows deleted)
    cache_stats()                        -> dict
"""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Modes that are eligible for caching ────────────────────────────────────────
CACHEABLE_MODES: frozenset[str] = frozenset({"prelims", "mains"})

# ── Module-level config (populated by init_cache) ──────────────────────────────
_db_path: Path | None      = None
_ttl_seconds: int          = 604_800   # 7 days
_max_entries: int          = 1_000
_enabled: bool             = True


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cache_key(query: str, mode: str) -> str:
    """Stable sha256 key from normalised query + mode."""
    raw = f"{query.strip().lower()}|{mode.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    """Open a short-lived WAL connection to the SQLite cache DB."""
    if _db_path is None:
        raise RuntimeError("Response cache not initialised. Call init_cache() first.")
    conn = sqlite3.connect(str(_db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the cache table if it doesn't already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS response_cache (
            cache_key   TEXT PRIMARY KEY,
            query       TEXT NOT NULL,
            mode        TEXT NOT NULL,
            payload     TEXT NOT NULL,
            created_at  REAL NOT NULL,
            expires_at  REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expires ON response_cache (expires_at)"
    )
    conn.commit()


# ── Public API ─────────────────────────────────────────────────────────────────

def init_cache(
    db_path: Path,
    ttl_seconds: int = 604_800,
    max_entries: int = 1_000,
    enabled: bool = True,
) -> None:
    """
    Initialise the cache. Must be called once at application startup.

    Args:
        db_path:     Path to the SQLite file (created automatically).
        ttl_seconds: Seconds before a cached entry expires (default 7 days).
        max_entries: Max rows kept in the table; oldest are pruned on insert.
        enabled:     Master on/off switch. When False, get/set are no-ops.
    """
    global _db_path, _ttl_seconds, _max_entries, _enabled
    _db_path     = Path(db_path)
    _ttl_seconds = ttl_seconds
    _max_entries = max_entries
    _enabled     = enabled

    _db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _ensure_table(conn)

    logger.info(
        f"[ResponseCache] Initialised — path='{_db_path}', "
        f"ttl={ttl_seconds}s ({ttl_seconds // 86400}d), "
        f"max_entries={max_entries}, enabled={enabled}"
    )


def get_response(query: str, mode: str) -> dict[str, Any] | None:
    """
    Look up a cached response.

    Returns:
        The cached payload dict if found and not expired, else None.
        Also returns None when cache is disabled or mode is not cacheable.
    """
    if not _enabled or mode not in CACHEABLE_MODES:
        return None

    key = _cache_key(query, mode)
    now = time.time()

    try:
        with _connect() as conn:
            _ensure_table(conn)
            # Opportunistically evict expired rows
            conn.execute("DELETE FROM response_cache WHERE expires_at <= ?", (now,))
            conn.commit()

            row = conn.execute(
                "SELECT payload FROM response_cache WHERE cache_key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()

        if row:
            payload = json.loads(row[0])
            logger.info(f"[ResponseCache] HIT — query='{query[:60]}' mode='{mode}'")
            return payload

        logger.debug(f"[ResponseCache] MISS — query='{query[:60]}' mode='{mode}'")
        return None

    except Exception as exc:
        logger.warning(f"[ResponseCache] get_response error (returning None): {exc}")
        return None


def set_response(query: str, mode: str, payload: dict[str, Any]) -> None:
    """
    Store a response in the cache.

    Skips storing when:
      - Cache is disabled
      - Mode is not cacheable
      - payload has answered=False or gated=True (no point caching failures)
    """
    if not _enabled or mode not in CACHEABLE_MODES:
        return
    if not payload.get("answered", False) or payload.get("gated", False):
        logger.debug(
            f"[ResponseCache] Skipping cache write — "
            f"answered={payload.get('answered')}, gated={payload.get('gated')}"
        )
        return

    key     = _cache_key(query, mode)
    now     = time.time()
    expires = now + _ttl_seconds

    try:
        with _connect() as conn:
            _ensure_table(conn)

            conn.execute(
                """
                INSERT INTO response_cache (cache_key, query, mode, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload    = excluded.payload,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (key, query.strip(), mode.strip(), json.dumps(payload), now, expires),
            )

            # LRU eviction: prune oldest entries if we've exceeded max_entries
            count = conn.execute(
                "SELECT COUNT(*) FROM response_cache"
            ).fetchone()[0]
            if count > _max_entries:
                excess = count - _max_entries
                conn.execute(
                    """
                    DELETE FROM response_cache WHERE cache_key IN (
                        SELECT cache_key FROM response_cache
                        ORDER BY created_at ASC LIMIT ?
                    )
                    """,
                    (excess,),
                )
                logger.debug(f"[ResponseCache] Evicted {excess} oldest entries (max={_max_entries})")

            conn.commit()
        logger.info(
            f"[ResponseCache] STORED — query='{query[:60]}' mode='{mode}' "
            f"ttl={_ttl_seconds}s"
        )
    except Exception as exc:
        logger.warning(f"[ResponseCache] set_response error (skipping): {exc}")


def clear_cache() -> int:
    """
    Delete all entries from the cache.

    Returns:
        Number of rows deleted.
    """
    try:
        with _connect() as conn:
            _ensure_table(conn)
            cursor = conn.execute("DELETE FROM response_cache")
            conn.commit()
            deleted = cursor.rowcount
        logger.info(f"[ResponseCache] Cleared {deleted} entries.")
        return deleted
    except Exception as exc:
        logger.warning(f"[ResponseCache] clear_cache error: {exc}")
        return 0


def cache_stats() -> dict[str, Any]:
    """
    Return basic stats about the current cache state.

    Returns:
        Dict with total_entries, expired_entries, enabled, db_path, ttl_seconds.
    """
    try:
        now = time.time()
        with _connect() as conn:
            _ensure_table(conn)
            total   = conn.execute("SELECT COUNT(*) FROM response_cache").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM response_cache WHERE expires_at <= ?", (now,)
            ).fetchone()[0]
        return {
            "enabled":         _enabled,
            "total_entries":   total,
            "live_entries":    total - expired,
            "expired_entries": expired,
            "max_entries":     _max_entries,
            "ttl_seconds":     _ttl_seconds,
            "db_path":         str(_db_path),
        }
    except Exception as exc:
        return {"error": str(exc), "enabled": _enabled}
