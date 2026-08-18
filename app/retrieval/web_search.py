"""
app/retrieval/web_search.py
────────────────────────────
DuckDuckGo web search fallback for low-confidence queries (< 0.50).

Uses the `duckduckgo-search` Python library (free, no API key required).
Returns web snippets formatted as chunk dicts compatible with the reranker.

Public API:
    web_search(query, max_results) -> list[dict]
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def web_search(
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    Perform a DuckDuckGo web search and return results as chunk dicts.

    Args:
        query:       The user's query string.
        max_results: Maximum number of web results to retrieve.

    Returns:
        List of chunk dicts with keys:
            {
                "chunk_id":  str,            # e.g. "web_001"
                "text":      str,            # title + snippet combined
                "score":     float,          # rank-based score (1.0 → 0.0)
                "metadata":  {
                    "url":   str,
                    "title": str,
                },
                "source":    "duckduckgo",
            }
        Returns [] on any failure.
    """
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=max_results))

        if not hits:
            logger.info(f"WebSearch: No DuckDuckGo results for query: '{query[:60]}'")
            return []

        # Build normalized chunk dicts
        for idx, hit in enumerate(hits):
            title   = hit.get("title", "")
            body    = hit.get("body", "")
            url     = hit.get("href", "")
            text    = f"{title}\n{body}".strip()

            # Score based on rank (first result = 1.0, decays linearly)
            rank_score = round(1.0 - (idx / max(len(hits), 1)), 4)

            results.append({
                "chunk_id": f"web_{idx + 1:03d}",
                "text":     text,
                "score":    rank_score,
                "metadata": {
                    "url":   url,
                    "title": title,
                },
                "source": "duckduckgo",
            })

        logger.info(
            f"WebSearch: DuckDuckGo returned {len(results)} results for "
            f"query: '{query[:60]}'"
        )
        return results

    except ImportError:
        logger.error(
            "WebSearch: 'duckduckgo-search' is not installed. "
            "Run: pip install duckduckgo-search"
        )
        return []

    except Exception as exc:
        logger.error(f"WebSearch: DuckDuckGo search failed: {exc}")
        return []
