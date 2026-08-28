# 📚 UPSC RAG Chatbot

A **production-grade Retrieval-Augmented Generation (RAG)** system built specifically for **UPSC exam preparation**. It ingests UPSC study material PDFs, embeds them into a vector database, and lets you ask questions in natural language — with conversation memory, anti-hallucination safeguards, and live web search fallback.

---

## 🧠 What Does This Chatbot Do?

When you ask a UPSC question, the system:

1. **Understands your intent** — classifies whether the question is from the ingested study corpus or needs a live web search.
2. **Condenses follow-up queries** — if you ask *"What is its current status?"*, it rewrites it into a standalone query like *"Status of ISRO's Gaganyaan mission"* using conversational context.
3. **Retrieves the best context** — either from the Qdrant vector database (ingested UPSC PDFs) or from live web scraping (DuckDuckGo + SearXNG).
4. **Generates a grounded answer** — using a Gemini or Groq LLM, strictly based on the retrieved context (no hallucination).
5. **Remembers your conversation** — stores the last 5 turns of chat history per session and injects it into the prompt for multi-turn dialogue.
6. **Cites its sources** — every answer includes clickable citations so you can verify the information.

---

## 🏗️ System Architecture

```
                        ┌─────────────────────────────┐
                        │       upsc_ui.html           │
                        │   (Browser Chat Interface)   │
                        └──────────────┬──────────────┘
                                       │  POST /api/v1/query
                                       ▼
                        ┌─────────────────────────────┐
                        │     FastAPI Application      │
                        │      (app/main.py)            │
                        └──────────────┬──────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
                    │          Query Processing             │
                    │                                       │
                    │  1. Load Conversation History (DB)    │
                    │  2. Condense Follow-up Queries (LLM)  │
                    │  3. Classify Query Intent (LLM)       │
                    └──────────┬──────────────────┬────────┘
                               │                  │
               ┌───────────────▼──┐          ┌────▼───────────────┐
               │  HIGH CONFIDENCE  │          │  LOW CONFIDENCE    │
               │  (UPSC Corpus)    │          │  (General / Live)  │
               │                  │          │                    │
               │  Qdrant Search   │          │  Web Search        │
               │  + Cross-Encoder │          │  (DuckDuckGo +     │
               │    Reranking     │          │   SearXNG)         │
               └───────────┬──────┘          └──────┬─────────────┘
                           │                         │
                           └────────────┬────────────┘
                                        ▼
                            ┌───────────────────────┐
                            │   LLM Response Gen    │
                            │  (Gemini / Groq LLM)  │
                            │  with History + Ctx   │
                            └───────────┬───────────┘
                                        │
                            ┌───────────▼───────────┐
                            │  Save to Chat History  │
                            │  (PostgreSQL DB)        │
                            └───────────────────────┘
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 **Hybrid Retrieval** | Vector DB search (Qdrant) + Live web fallback (DuckDuckGo) |
| 🧩 **Query Classification** | LLM classifies queries as Corpus-bound or Web-search |
| 📊 **Cross-Encoder Reranking** | MS-MARCO MiniLM reranker for precise top-K chunk selection |
| 💬 **Conversation Memory** | Sliding window of last 5 turns persisted in PostgreSQL |
| 🔄 **Query Condensation** | Rewrites pronouns in follow-ups into standalone queries |
| 📰 **Current Affairs Mode** | Scrapes live news articles for recent events |
| 🛡️ **Anti-Hallucination Layer** | LLM is instructed to answer only from retrieved context |
| 📌 **Source Citations** | Every answer includes a clickable list of sources |
| 🌊 **Streaming Responses** | Server-Sent Events (SSE) endpoint for token-level streaming |
| 📄 **PDF Ingestion Pipelines** | Two ingestion engines for digital and scanned PDFs |

---

## 🚀 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents` | Ingest digital PDFs via local Docling engine |
| `POST` | `/api/v2/documents` | Ingest scanned PDFs via Gemini Flash VLM |
| `POST` | `/api/v1/query` | Query the RAG system (standard JSON response) |
| `POST` | `/api/v1/query/stream` | Query the RAG system (SSE streaming response) |
| `GET` | `/health` | Service health check |
| `GET` | `/docs` | Interactive Swagger UI |

---

## 📁 Repository Structure

```
RAG-main/
├── app/
│   ├── api/routes/
│   │   ├── documents.py         # POST /api/v1/documents — Docling ingestion
│   │   ├── extract_page.py      # POST /api/v2/documents — Gemini VLM ingestion
│   │   ├── query.py             # POST /api/v1/query — RAG query with memory
│   │   └── query_stream.py      # POST /api/v1/query/stream — SSE streaming
│   ├── core/config.py           # Environment configuration loader
│   ├── database/
│   │   ├── session.py           # SQLAlchemy connection setup
│   │   ├── models.py            # PostgreSQL models (Documents + ChatMessages)
│   │   └── repository.py        # Database CRUD helpers
│   ├── retrieval/
│   │   ├── query_classifier.py  # LLM query intent classifier
│   │   ├── retrieval_router.py  # Routes to vector search or web search
│   │   ├── vector_search.py     # Qdrant hybrid vector lookup
│   │   ├── reranker.py          # MS-MARCO cross-encoder reranker
│   │   ├── web_search.py        # DuckDuckGo + SearXNG web scraper
│   │   ├── search_pipeline.py   # Current affairs live article pipeline
│   │   ├── prompts.py           # System prompt templates (Prelims/Mains/CA)
│   │   └── generator.py         # LLM response gen + conversation memory
│   ├── services/
│   │   ├── storage_service.py      # PDF storage handler
│   │   ├── extraction_service.py   # Docling bridge + QA audit
│   │   ├── page_extraction_service.py # Gemini page-by-page extractor
│   │   ├── preprocessing_service.py   # Layout-aware chunking
│   │   ├── embedding_service.py       # BGE SentenceTransformer embeddings
│   │   ├── qdrant_service.py          # Qdrant upsert + collection manager
│   │   └── ingest_pipeline.py         # Core ingestion orchestrator
│   └── main.py                  # FastAPI entry point + DB lifespan
├── extraction/                  # Docling + Gemini VLM parsing modules
├── preprocessing/               # Layout-aware cleaning + chunking engine
├── tests/                       # Test suite (52 tests)
│   ├── test_conversation_memory.py  # Chat/memory persistence tests
│   ├── test_prompt_selection.py     # Prompt routing & formatting tests
│   ├── test_search_pipeline.py      # Web search pipeline tests
│   ├── test_metrics.py              # Evaluation metric tests
│   └── test_article_cache.py        # Article caching tests
├── upsc_ui.html                 # Browser-based chat UI
├── docker-compose.yml           # PostgreSQL + Qdrant services
├── .env.example                 # Environment configuration template
└── requirements_api.txt         # API runtime dependencies
```

---

## ⚙️ Quick Start

### 1. Start Infrastructure (Docker)

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** at `localhost:5432` — stores document metadata and chat history
- **Qdrant Vector DB** at `localhost:6333` — stores embedded UPSC PDF chunks

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/upsc_rag
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5

# LLM keys (use at least one)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-specdec
```

### 3. Install Dependencies

```bash
pip install -r requirements_api.txt
```

### 4. Start the API Server

```bash
uvicorn app.main:app --reload
```

| Service | URL |
|---|---|
| **Chat UI** | Open `upsc_ui.html` directly in your browser |
| **Swagger Docs** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |

---

## 💬 Using the Chat UI

1. Open `upsc_ui.html` in your browser.
2. Select the **query mode**: Prelims, Mains, or Current Affairs.
3. Type your UPSC question and click **Ask**.
4. Ask follow-up questions — the chatbot remembers the conversation context.
5. Click **Clear History** to start a fresh session.

### Example Multi-Turn Conversation

```
You:  What is ISRO's Gaganyaan mission?
Bot:  Gaganyaan is India's first human spaceflight programme...

You:  What is its current status?
Bot:  (automatically understands "its" = Gaganyaan)
      As of the latest updates, ISRO completed the TV-D1 abort test...
```

---

## 🔍 Retrieval Modes

| Mode | When Used | Source |
|---|---|---|
| **Prelims** | Factual, MCQ-style questions | Ingested PDF corpus |
| **Mains** | Essay/analytical questions | Ingested PDF corpus |
| **Current Affairs** | Recent news, schemes, events | Live web scraping |
| **Web Fallback** | Out-of-domain or low-confidence | DuckDuckGo + SearXNG |

---

## 📄 PDF Ingestion Engines

| Engine | Endpoint | Best For |
|---|---|---|
| **Docling v2** (Local) | `POST /api/v1/documents` | Digital, selectable-text PDFs |
| **Gemini Flash VLM** (Cloud) | `POST /api/v2/documents` | Scanned, multi-column, image PDFs |

Both engines run through the same status pipeline:

```
registered → extracting → extracted → preprocessing → preprocessed → embedding → ingested
```

---

## 📊 Extraction Quality

Evaluated across **77 active UPSC PDFs**:

| Metric | Result |
|---|---|
| Average Confidence Score | **95.9%** |
| Page Coverage | **103.7%** (OCR fallback guaranteed) |
| Documents ready for RAG | **77 / 77 (100%)** |

---

## ⚡ Performance Tuning

Adjust these `.env` variables to tune retrieval speed vs. quality:

| Variable | Default | Effect |
|---|---|---|
| `RETRIEVAL_CANDIDATE_K` | `10` | Lower = faster reranking |
| `RERANKER_MODEL_NAME` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Use MiniLM for CPU speed |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | Lower = fewer web searches |

---

## 🧪 Running Tests

```bash
# Run all 52 tests
python -m pytest

# Run only conversation memory tests
python -m pytest tests/test_conversation_memory.py -v

# Run only prompt routing tests
python -m pytest tests/test_prompt_selection.py -v
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **API Framework** | FastAPI |
| **Vector Database** | Qdrant |
| **Relational Database** | PostgreSQL + SQLAlchemy |
| **Embedding Model** | BAAI/bge-base-en-v1.5 (SentenceTransformers) |
| **Reranker Model** | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| **LLM (Generation)** | Google Gemini / Groq (Llama 3.3) |
| **PDF Extraction** | Docling v2 + Gemini Flash VLM |
| **Web Search** | DuckDuckGo + SearXNG |
| **Frontend** | Vanilla HTML + CSS + JavaScript |
