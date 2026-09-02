# ?? UPSC RAG — Unified Current Affairs & Speed Optimization Plan

> **Status:** Planning ? Implementation
> **Scope:** Current Affairs (CA) Engine Overhaul + System-wide Speed Optimizations
> **Principle:** Zero disruption to existing Prelims, Mains, or PDF ingestion pipelines.

---

## ?? Executive Summary

We are transforming the existing disconnected Current Affairs mode into a **Unified, Self-Hosted Current Affairs Hub** that:
1. Automatically scrapes and indexes *The Hindu* & *PIB* every morning at **06:00 AM** directly into a new **`current_affairs_collection`** in Qdrant.
2. Adds **3 dynamic sub-modes** under Current Affairs: `MCQ`, `Summary`, and `Explanation`.
3. Removes the reliance on DuckDuckGo for 90% of CA queries by serving them instantly from the pre-indexed local vector store.
4. Achieves **~6x faster response times** through a set of targeted optimizations.

---

## ??? Files Involved

### Modified Files (6)
| File | Change Type | Summary |
|---|---|---|
| `app/core/config.py` | Modify | Add `current_affairs_collection`, news scraper config, reduce candidate K |
| `app/retrieval/prompts.py` | Modify | Add 3 CA sub-mode prompts (MCQ, Summary, Explain); update `get_prompt()` |
| `app/api/routes/query.py` | Modify | Add `sub_mode` field to `QueryRequest`; pass it through the pipeline |
| `app/retrieval/retrieval_router.py` | Modify | Local Qdrant CA lookup first; DuckDuckGo only as fallback; parallel classify+search |
| `app/retrieval/response_cache.py` | Modify | Add `current_affairs_summary` to cacheable modes (6h TTL) |
| `app/main.py` | Modify | Register APScheduler 06:00 AM cron job + ensure `current_affairs_collection` |

### New Files (1)
| File | Description |
|---|---|
| `app/services/news_scraper_service.py` | Full daily news scraper: scrapes -> chunks -> embeds -> upserts into Qdrant. Cleans up news older than 365 days. |

---

## ?? Detailed Change Specifications

---

### 1. `app/core/config.py` DONE

**What changed:**
```diff
# Qdrant collections
QDRANT_COLLECTION_MAP = {
    "History":        "history_collection",
    "Anthropology":   "anthropology_collection",
+   "CurrentAffairs": "current_affairs_collection",
}

+ CA_NEWS_COLLECTION: str = "current_affairs_collection"

# Candidate chunks (speed optimization)
- RETRIEVAL_CANDIDATE_K: int = 10
+ RETRIEVAL_CANDIDATE_K: int = 5    # 2x faster reranker

# News scraper schedule config (new)
+ NEWS_SCRAPER_CRON_HOUR:   int = 6     # 06:00 AM daily
+ NEWS_SCRAPER_CRON_MINUTE: int = 0
+ NEWS_RETENTION_DAYS:      int = 365   # 1-year rolling window
+ NEWS_MAX_ARTICLES:        int = 8     # per source per run
```

---

### 2. `app/services/news_scraper_service.py` NEW FILE

**Purpose:** Automated daily news scraper that feeds directly into Qdrant.

**Full Pipeline:**
```
06:00 AM Trigger
    |
    |-- fetch_hindu_links()    -> Top 8 links from thehindu.com
    |-- fetch_pib_links()      -> Top 8 links from pib.gov.in
    |
    |-- scrape_article(url)    -> Extract title + body text (BeautifulSoup)
    |
    |-- chunk_article()        -> Split into 300-token chunks with metadata:
    |                              { date, source_url, title, gs_category }
    |
    |-- embed_chunks()         -> BAAI/bge-base-en-v1.5 (same model already loaded)
    |
    |-- upsert_to_qdrant()     -> SHA-256 URL hash as point_id (no duplicates)
    |
    `-- cleanup_old_vectors()  -> Delete vectors with date < (today - 365 days)
```

**Admin Trigger Endpoint:**
```
POST /api/v1/admin/sync-news   <- Manually trigger sync anytime
```

---

### 3. `app/retrieval/prompts.py` PENDING

**What changes:**
- Add 3 new CA sub-mode prompt templates.
- Update `get_prompt()` to accept optional `sub_mode`.

| Sub-Mode | Output Format |
|---|---|
| `summary` (default) | Headline -> 3-bullet key takeaways -> Exam Relevance -> Read More link |
| `mcq` | 3-5 statement-based UPSC Prelims MCQs + answer key + explanation |
| `explain` | Mains-style: Context -> Policy -> Critical Analysis -> Way Forward |
| `mains` | Full existing Current Affairs deep-dive prompt (unchanged) |

---

### 4. `app/api/routes/query.py` PENDING

**What changes:** Add `sub_mode` field to `QueryRequest`.

```python
sub_mode: Optional[str] = Field(
    default="summary",
    description="CA output style: 'summary' | 'mcq' | 'explain' | 'mains'"
)
```

Same change applied in `query_stream.py` for SSE streaming.

---

### 5. `app/retrieval/retrieval_router.py` PENDING

**New CA routing logic:**
```
Current (Old):
    mode="current_affairs" -> ALWAYS DuckDuckGo (4-6s) -> Rerank -> LLM

New (Optimized):
    mode="current_affairs"
        |
        v
    Search local "current_affairs_collection" (pre-indexed morning news)
        |
        |-- [Found, score >= 0.50] -> Instant Qdrant answer (<1s)
        |
        `-- [Not Found / Low Score] -> DuckDuckGo fallback (rare, ~5s)
```

**Also adds parallel classify + search:**
```python
# AFTER (Parallel asyncio.gather):
classification, candidates = await asyncio.gather(
    classify_query_async(query),
    vector_search_ca_async(query),
)
# Saves ~0.5s per query
```

---

### 6. `app/retrieval/response_cache.py` PENDING

```diff
- CACHEABLE_MODES: frozenset = frozenset({"prelims", "mains"})
+ CACHEABLE_MODES: frozenset = frozenset({"prelims", "mains", "current_affairs_summary"})
```

---

### 7. `app/main.py` PENDING

Register APScheduler 06:00 AM cron + admin sync endpoint.

---

## ? Speed Optimization Summary

| Optimization | File | Time Saved | Status |
|---|---|---|---|
| Local Qdrant CA Lookup (no DuckDuckGo) | `retrieval_router.py` | ~4s per CA query | PENDING |
| Parallel Classify + Vector Search | `retrieval_router.py` | ~0.5s per query | PENDING |
| Reduce Candidate K: 10 -> 5 | `config.py` | ~0.4s reranker | DONE |
| SSE Streaming (already exists) | `query_stream.py` | Instant perceived response | EXISTS |
| CA Summary Caching (6h TTL) | `response_cache.py` | ~5s -> 20ms on repeat | PENDING |
| Groq as Primary Generator | `generator.py` | ~2s generation | PENDING |

---

## ??? Safety Guarantees

- Prelims & Mains queries: Completely unaffected.
- PDF ingestion pipeline: /api/v1/documents and /api/v2/documents untouched.
- Existing Qdrant data: `history_collection` and `anthropology_collection` are never modified.
- Duplicate prevention: SHA-256 hash of each article URL used as Qdrant point ID.
- 1-Year Rolling Window: Vectors older than 365 days auto-deleted daily (~75 MB total).

---

## ?? New Dependency

```bash
pip install apscheduler
```

Add to `requirements_api.txt`:
```
apscheduler>=3.10.4
```

---

## ? Implementation Checklist

- [x] `config.py` - Add `current_affairs_collection`, scraper config, reduce K
- [ ] `app/services/news_scraper_service.py` - Create new scraper service
- [ ] `app/retrieval/prompts.py` - Add MCQ, Summary, Explain sub-mode prompts
- [ ] `app/api/routes/query.py` - Add `sub_mode` field to `QueryRequest`
- [ ] `app/api/routes/query_stream.py` - Mirror `sub_mode` field for SSE
- [ ] `app/retrieval/retrieval_router.py` - Local CA Qdrant lookup + parallel search
- [ ] `app/retrieval/response_cache.py` - Enable CA summary caching
- [ ] `app/main.py` - Register APScheduler + admin sync endpoint
