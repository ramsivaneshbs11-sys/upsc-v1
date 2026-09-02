# 📚 UPSC RAG & Current Affairs AI Platform

A **production-grade Retrieval-Augmented Generation (RAG)** system built specifically for **UPSC Civil Services Examination preparation**. It combines deep syllabus-grounded PDF textbook retrieval with an automated **Daily News & Current Affairs Engine** (MCQ practice, Mains answer generation, executive summaries, and live source verification).

---

## 🧠 System Overview & Capabilities

```
                                    ┌─────────────────────────────┐
                                    │       upsc_ui.html          │
                                    │   (Browser Chat Interface)  │
                                    └──────────────┬──────────────┘
                                                   │ POST /api/v1/query
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │     FastAPI Application     │
                                    │       (app/main.py)         │
                                    └──────────────┬──────────────┘
                                                   │
                                ┌──────────────────▼───────────────────┐
                                │          Query Processing            │
                                │  1. Load Conversation History (DB)   │
                                │  2. Condense Follow-up Queries (LLM) │
                                │  3. Classify Mode / Syllabus Paper   │
                                └──────────────────┬───────────────────┘
                                                   │
                  ┌────────────────────────────────┼────────────────────────────────┐
                  ▼                                ▼                                ▼
       ┌─────────────────────┐          ┌─────────────────────┐          ┌─────────────────────┐
       │   📝 PRELIMS MODE   │          │    📄 MAINS MODE    │          │ 🌐 CURRENT AFFAIRS  │
       │ (Textbooks & PDFs)  │          │ (Analytical Papers) │          │  (Daily News & Web) │
       └──────────┬──────────┘          └──────────┬──────────┘          └──────────┬──────────┘
                  │                                │                                │
                  └────────────────┬───────────────┘                                │
                                   │                                                │
                     ┌─────────────▼─────────────┐                    ┌─────────────▼─────────────┐
                     │ Qdrant Vector Search      │                    │ 1. Qdrant Daily News Store│
                     │ (History / Anthropology)  │                    │ 2. DuckDuckGo / SearXNG   │
                     └─────────────┬─────────────┘                    └─────────────┬─────────────┘
                                   │                                                │
                                   └───────────────────────┬────────────────────────┘
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │ MS-MARCO MiniLM Reranker    │
                                            │ (Top-5 High Scoring Chunks) │
                                            └──────────────┬──────────────┘
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │ LLM Response Generation     │
                                            │ (Gemini 2.5 / Groq LLMs)    │
                                            └──────────────┬──────────────┘
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │ Answer + Clickable Citations│
                                            │ (Persisted to PostgreSQL)   │
                                            └─────────────────────────────┘
```

---

## ✨ Core Features

| Feature | Description |
|---|---|
| 🔍 **Multi-Mode RAG Retrieval** | Dedicated routing for **Prelims (Static)**, **Mains (Analytical)**, and **Current Affairs**. |
| 📰 **Unified Current Affairs Hub** | Background scraper (06:00 AM) auto-indexes *The Hindu* and *PIB* directly into Qdrant for **<1s latency**. |
| 🎯 **Dynamic Sub-Modes** | Current Affairs supports **MCQs Practice**, **News Summary (3-points)**, and **Detailed Explanation**. |
| 🔗 **Source Verification** | Every response includes clickable **"Read More"** links pointing to official government gazettes & editorial pages. |
| ⚡ **Cross-Encoder Reranking** | Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` for precise semantic scoring of retrieved passages. |
| 💬 **Conversational Memory** | Sliding window of recent turns stored in PostgreSQL with intelligent pronoun condensation. |
| 🛡️ **Anti-Hallucination Guardrails** | Strict citation grounding enforcing that answers are synthesized exclusively from verified context. |
| 🌊 **Server-Sent Events (SSE)** | Live token-level streaming endpoint (`/api/v1/query/stream`) with real-time pipeline status indicators. |
| 📄 **Dual PDF Ingestion Engines** | Specialized parsing for digital PDFs (Docling) and scanned handwritten notes (Gemini VLM). |

---

## 📁 Repository Structure

```
RAG-main/
├── app/
│   ├── api/routes/
│   │   ├── documents.py            # POST /api/v1/documents — Docling digital PDF ingestion
│   │   ├── extract_page.py         # POST /api/v2/documents — Gemini VLM scanned PDF ingestion
│   │   ├── query.py                # POST /api/v1/query — Standard RAG query endpoint
│   │   └── query_stream.py         # POST /api/v1/query/stream — SSE real-time streaming endpoint
│   ├── core/
│   │   ├── config.py               # Environment variables, Qdrant collections & model configs
│   │   └── response_cache.py       # SQLite response caching engine (24h TTL)
│   ├── database/
│   │   ├── session.py              # SQLAlchemy engine & session factory
│   │   ├── models.py               # PostgreSQL schema (Document & ChatMessage tables)
│   │   └── repository.py           # Database CRUD helpers
│   ├── retrieval/
│   │   ├── query_classifier.py     # Intent classification & routing engine
│   │   ├── vector_search.py        # Qdrant hybrid similarity search
│   │   ├── reranker.py             # Cross-encoder semantic reranking
│   │   ├── search_pipeline.py      # DuckDuckGo + SearXNG live web search pipeline
│   │   ├── article_cache.py        # SQLite cache for scraped web articles (6h TTL)
│   │   ├── prompts.py              # Exam-specific system prompt templates
│   │   └── generator.py            # Multi-LLM synthesis (Gemini 2.5 / Groq)
│   ├── services/
│   │   ├── embedding_service.py    # BAAI/bge-base-en-v1.5 sentence embeddings
│   │   ├── qdrant_service.py       # Qdrant collection management & vector upserts
│   │   └── ingest_pipeline.py      # Core document indexing orchestrator
│   └── main.py                     # FastAPI application entry point with lifespan lifecycle
├── extraction/                     # Docling layout parsing & column re-ordering logic
├── preprocessing/                  # Layout-aware chunking & text cleaning engine
├── tests/                          # Automated test suite (50+ unit & integration tests)
├── upsc_ui.html                    # Interactive browser frontend for querying & testing
├── docker-compose.yml              # PostgreSQL + Qdrant container configurations
├── requirements_api.txt            # Production Python dependencies
└── .env.example                    # Environment variables template
```

---

## ⚙️ Quick Start Guide

### 1. Start Database Containers (Docker)

Make sure **Docker Desktop** is running, then start **PostgreSQL** and **Qdrant**:

```powershell
docker-compose up -d
```

* **PostgreSQL:** Running on `localhost:5432` (Stores document metadata & chat memory)
* **Qdrant Vector DB:** Running on `localhost:6333` (Stores embedded PDF chunks & current affairs vectors)

---

### 2. Environment Configuration

Create a `.env` file in the root directory (or copy from `.env.example`):

```env
# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/upsc_rag

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedding Model
EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5

# LLM API Keys (At least one required)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Reranker Model
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2
```

---

### 3. Install Python Dependencies

```powershell
pip install -r requirements_api.txt
```

---

### 4. Start the Application Server

Launch the FastAPI backend with Uvicorn:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| Service | Access URL |
|---|---|
| **Chat Interface** | Open [`upsc_ui.html`](file:///c:/Users/vishn/Downloads/RAG-main/RAG-main/upsc_ui.html) directly in your browser |
| **Interactive Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Health Check Endpoint** | [http://localhost:8000/health](http://localhost:8000/health) |

---

## 🚀 API Reference

### 1. Query Endpoints

#### `POST /api/v1/query` — Standard RAG Query
Processes a question and returns a complete JSON response with citations and memory context.

**Request Body:**
```json
{
  "query": "Explain the major features of the Indus Valley Civilization urban planning.",
  "mode": "prelims",
  "session_id": "session_user_123"
}
```

**Response Body:**
```json
{
  "answer": "The Indus Valley Civilization demonstrated advanced town planning characterized by...",
  "sources": [
    {
      "source": "Ancient_History_NCERT.pdf",
      "page": 42,
      "score": 0.892
    }
  ],
  "latency_ms": 780,
  "cache_hit": false
}
```

#### `POST /api/v1/query/stream` — Real-Time SSE Stream
Streams pipeline stages and real-time generation progress to the user interface.

---

### 2. Current Affairs & Multi-Mode Queries

Under Current Affairs, select a specialized `sub_mode` to tailor the output:

```json
{
  "query": "Recent Supreme Court judgment on Electoral Bonds",
  "mode": "current_affairs",
  "sub_mode": "mcq"  // Options: "summary" | "mains" | "mcq" | "explain"
}
```

* **`summary`:** 3-bullet executive overview of the event with key takeaways.
* **`mains`:** Structured 250-word analytical answer (Context $\rightarrow$ Pros/Cons/Issues $\rightarrow$ Way Forward).
* **`mcq`:** 3–5 UPSC Prelims-style statement questions with answer key and rationale.
* **`explain`:** Simple, beginner-friendly conceptual breakdown.

---

### 3. Document Ingestion Endpoints

* **Digital PDFs:** `POST /api/v1/documents` — Parses digital PDFs using Docling layout analyzer.
* **Scanned/Image PDFs:** `POST /api/v2/documents` — Parses scanned, low-contrast, or handwritten notes using Gemini VLM.

---

### 4. Admin & Cache Management

* **`GET /api/v1/cache/stats`:** Returns live response cache metrics (live entries, memory size, TTL).
* **`DELETE /api/v1/cache`:** Clears the entire response cache database.

---

## 🧪 Running Automated Tests

Run the complete test suite (50+ tests covering memory, reranking, prompts, and cache):

```powershell
pytest tests/ -v
```

---

## 📄 License
This project is licensed under the MIT License.
