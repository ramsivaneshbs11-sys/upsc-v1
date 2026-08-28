"""
tests/test_article_cache.py
────────────────────────────
Unit tests for app/retrieval/article_cache.py

Covers:
  - Cache miss returns None
  - Store + get returns the stored content
  - TTL expiry evicts the entry (memory backend)
  - LRU eviction when maxsize is exceeded (memory backend)
  - SQLite backend persists across cache instances
  - clear_cache() wipes all entries
"""

import time
import pytest

# ── Force memory backend for all tests ────────────────────────────────────────
import os
os.environ.setdefault("ARTICLE_CACHE_BACKEND", "memory")
os.environ.setdefault("ARTICLE_CACHE_MAXSIZE", "3")
os.environ.setdefault("ARTICLE_CACHE_TTL_SECONDS", "2")   # 2 s TTL for fast expiry tests


from app.retrieval.article_cache import (
    _MemoryCache,
    _SQLiteCache,
    get_article,
    store_article,
    clear_cache,
)


# ── _MemoryCache unit tests ───────────────────────────────────────────────────

class TestMemoryCache:
    def setup_method(self):
        self.cache = _MemoryCache(maxsize=3, ttl=60)

    def test_miss_returns_none(self):
        assert self.cache.get("http://example.com/a") is None

    def test_store_and_get(self):
        self.cache.set("http://example.com/a", "content A")
        assert self.cache.get("http://example.com/a") == "content A"

    def test_ttl_expiry(self):
        short_ttl_cache = _MemoryCache(maxsize=10, ttl=1)
        short_ttl_cache.set("http://example.com/b", "content B")
        assert short_ttl_cache.get("http://example.com/b") == "content B"
        time.sleep(1.1)
        assert short_ttl_cache.get("http://example.com/b") is None

    def test_lru_eviction(self):
        """When maxsize=3, inserting a 4th item evicts the least recently used."""
        self.cache.set("url1", "c1")
        self.cache.set("url2", "c2")
        self.cache.set("url3", "c3")
        # Access url1 to make url2 the LRU
        self.cache.get("url1")
        self.cache.set("url4", "c4")   # should evict url2
        assert self.cache.get("url2") is None
        assert self.cache.get("url1") == "c1"
        assert self.cache.get("url3") == "c3"
        assert self.cache.get("url4") == "c4"

    def test_clear(self):
        self.cache.set("url1", "c1")
        self.cache.clear()
        assert self.cache.get("url1") is None

    def test_overwrite(self):
        self.cache.set("url1", "old")
        self.cache.set("url1", "new")
        assert self.cache.get("url1") == "new"


# ── _SQLiteCache unit tests ───────────────────────────────────────────────────

class TestSQLiteCache:
    def setup_method(self, tmp_path=None):
        import tempfile, pathlib
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.cache = _SQLiteCache(db_path=self.tmp_db, ttl=60)

    def teardown_method(self):
        import os
        try:
            os.remove(self.tmp_db)
        except FileNotFoundError:
            pass

    def test_miss_returns_none(self):
        assert self.cache.get("http://example.com/x") is None

    def test_store_and_get(self):
        self.cache.set("http://example.com/x", "article text")
        assert self.cache.get("http://example.com/x") == "article text"

    def test_persistence_across_instances(self):
        self.cache.set("http://example.com/persist", "persisted!")
        cache2 = _SQLiteCache(db_path=self.tmp_db, ttl=60)
        assert cache2.get("http://example.com/persist") == "persisted!"

    def test_ttl_expiry(self):
        short = _SQLiteCache(db_path=self.tmp_db, ttl=1)
        short.set("http://example.com/ttl", "val")
        time.sleep(1.1)
        assert short.get("http://example.com/ttl") is None

    def test_clear(self):
        self.cache.set("http://example.com/clr", "v")
        self.cache.clear()
        assert self.cache.get("http://example.com/clr") is None


# ── Public API smoke test ─────────────────────────────────────────────────────

def test_public_api_roundtrip():
    """get_article / store_article / clear_cache use the module-level cache."""
    clear_cache()
    assert get_article("http://test.com/article") is None
    store_article("http://test.com/article", "test content")
    assert get_article("http://test.com/article") == "test content"
    clear_cache()
    assert get_article("http://test.com/article") is None
