"""
tests/test_search_pipeline.py
──────────────────────────────
Unit tests for app/retrieval/search_pipeline.py

Covers:
  - build_site_filtered_query correctly prefixes site: operators
  - parallel_search merges DDG + SearXNG results and deduplicates by URL
  - DDG-only results are returned when SearXNG fails (and vice versa)
  - scrape_article returns cached content on second call (no network)
  - parallel_search returns empty list when both providers fail
"""

import os
import pytest
from unittest.mock import patch, MagicMock

os.environ["ARTICLE_CACHE_BACKEND"] = "memory"
os.environ["TRUSTED_SITES"] = "pib.gov.in,insightsias.com,civilsdaily.com"
os.environ["SEARCH_MAX_RESULTS"] = "3"

import app.core.config
app.core.config.TRUSTED_SITES = ["pib.gov.in", "insightsias.com", "civilsdaily.com"]
app.core.config.SEARCH_MAX_RESULTS = 3

import app.retrieval.search_pipeline
app.retrieval.search_pipeline.TRUSTED_SITES = ["pib.gov.in", "insightsias.com", "civilsdaily.com"]
app.retrieval.search_pipeline.SEARCH_MAX_RESULTS = 3

from app.retrieval.search_pipeline import (
    build_site_filtered_query,
    parallel_search,
    scrape_article,
    _duckduckgo_search,
    _searxng_search,
)
from app.retrieval.article_cache import clear_cache


# ── build_site_filtered_query ─────────────────────────────────────────────────

def test_build_site_filtered_query_includes_sites():
    result = build_site_filtered_query("Green Hydrogen Mission")
    assert "site:pib.gov.in" in result
    assert "site:insightsias.com" in result
    assert "Green Hydrogen Mission" in result


def test_build_site_filtered_query_empty_sites():
    with patch("app.retrieval.search_pipeline.TRUSTED_SITES", []):
        result = build_site_filtered_query("UPSC query")
        assert result == "UPSC query"


# ── parallel_search: deduplication ───────────────────────────────────────────

_DDG_RESULTS = [
    {"url": "http://pib.gov.in/a", "title": "PIB A", "snippet": "...", "rank": 0, "source": "duckduckgo"},
    {"url": "http://insightsias.com/b", "title": "Insights B", "snippet": "...", "rank": 1, "source": "duckduckgo"},
]
_SRX_RESULTS = [
    {"url": "http://pib.gov.in/a",        "title": "PIB A (dup)", "snippet": "...", "rank": 0, "source": "searxng"},
    {"url": "http://civilsdaily.com/c",   "title": "CivilsDaily C", "snippet": "...", "rank": 1, "source": "searxng"},
]


def test_parallel_search_deduplicates_urls():
    with (
        patch("app.retrieval.search_pipeline._duckduckgo_search", return_value=_DDG_RESULTS),
        patch("app.retrieval.search_pipeline._searxng_search",    return_value=_SRX_RESULTS),
        patch("app.retrieval.search_pipeline._bing_search",       return_value=[]),
        patch("app.retrieval.search_pipeline.scrape_article",     return_value="article text long enough"),
    ):
        chunks = parallel_search("Green Hydrogen")

    urls = [c["metadata"]["url"] for c in chunks]
    # Duplicate http://pib.gov.in/a should appear only once
    assert urls.count("http://pib.gov.in/a") == 1
    # All three unique URLs should be present
    assert len(chunks) == 3


def test_parallel_search_ddg_priority_over_searxng():
    """DDG results should appear before SearXNG-only results."""
    with (
        patch("app.retrieval.search_pipeline._duckduckgo_search", return_value=_DDG_RESULTS),
        patch("app.retrieval.search_pipeline._searxng_search",    return_value=_SRX_RESULTS),
        patch("app.retrieval.search_pipeline._bing_search",       return_value=[]),
        patch("app.retrieval.search_pipeline.scrape_article",     return_value="text text text text"),
    ):
        chunks = parallel_search("query")

    urls = [c["metadata"]["url"] for c in chunks]
    assert urls[0] == "http://pib.gov.in/a"       # DDG first
    assert urls[1] == "http://insightsias.com/b"  # DDG second
    assert urls[2] == "http://civilsdaily.com/c"  # SearXNG gap-fill


def test_parallel_search_searxng_only_fallback():
    with (
        patch("app.retrieval.search_pipeline._duckduckgo_search", return_value=[]),
        patch("app.retrieval.search_pipeline._searxng_search",    return_value=_SRX_RESULTS),
        patch("app.retrieval.search_pipeline._bing_search",       return_value=[]),
        patch("app.retrieval.search_pipeline.scrape_article",     return_value="enough text here"),
    ):
        chunks = parallel_search("query")

    assert len(chunks) == 2


def test_parallel_search_both_fail_returns_empty():
    with (
        patch("app.retrieval.search_pipeline._duckduckgo_search", return_value=[]),
        patch("app.retrieval.search_pipeline._searxng_search",    return_value=[]),
        patch("app.retrieval.search_pipeline._bing_search",       return_value=[]),
    ):
        chunks = parallel_search("query")

    assert chunks == []


# ── scrape_article: cache behaviour ──────────────────────────────────────────

def test_scrape_article_uses_cache_on_second_call():
    clear_cache()
    url = "http://test.example.com/article"

    fake_response = MagicMock()
    fake_response.text = "<html><body><p>Real article paragraph text here that is long enough.</p></body></html>"
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()

    with patch("app.retrieval.search_pipeline.http_requests.get", return_value=fake_response) as mock_get:
        first  = scrape_article(url)
        second = scrape_article(url)

    # get() should be called exactly once (second call hits cache)
    assert mock_get.call_count == 1
    assert first == second


def test_scrape_article_returns_empty_on_http_error():
    clear_cache()
    url = "http://blocked.example.com/article"
    with patch("app.retrieval.search_pipeline.http_requests.get", side_effect=Exception("HTTP 403")):
        result = scrape_article(url)
    assert result == ""
