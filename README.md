# 📚 UPSC AI Platform & Advanced RAG Engine

A production-grade, full-stack AI ecosystem designed specifically for **UPSC Civil Services Examination (CSE)** preparation. This platform combines an advanced **Retrieval-Augmented Generation (RAG)** pipeline grounded in standard UPSC textbooks and notes with an **Automated Daily Current Affairs Scraper**, an **Interactive MCQ Practice Engine**, an **Admin Management Portal**, and a **Modern Glassmorphic React Frontend**.

---

## 🏛️ System Architecture

```
                                  ┌──────────────────────────────────────────────────────────┐
                                  │                React + Vite Web Platform                 │
                                  │      (Chat Mentor, Daily News, MCQ Practice, Admin)      │
                                  └─────────────┬───────────────────────────────┬────────────┘
                                                │ REST API / SSE                │
                                                ▼                               ▼
                                  ┌───────────────────────────┐   ┌──────────────────────────┐
                                  │    FastAPI Application    │   │  Admin Portal (Static)   │
                                  │       (app/main.py)       │   │      (admin_page/)       │
                                  └─────────────┬─────────────┘   └──────────────────────────┘
                                                │
                     ┌──────────────────────────┼──────────────────────────┐
                     ▼                          ▼                          ▼
        ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
        │     RAG Query Engine    │ │   Daily News Engine     │ │   MCQ Practice Engine   │
        │  • Intent Classification│ │  • Automated Web Scraper│ │  • Subject-wise Topics  │
        │  • Dense Vector Search  │ │  • Daily Indexing (PIB) │ │  • Instant Explanations │
        │  • Cross-Encoder Rerank │ │  • Qdrant + MongoDB/JSON│ │  • Performance Tracking │
        │  • Multi-turn Memory    │ │  • 3-point Summarization│ │  • Prelims-style format │
        └────────────┬────────────┘ └───────────┬─────────────┘ └───────────┬─────────────┘
                     │                          │                           │
                     └──────────────────────────┼───────────────────────────┘
                                                ▼
                     ┌─────────────────────────────────────────────────────┐
                     │                 Storage & Model Tier                │
                     │  • Vector DB: Qdrant (Collections: upsc_rag, news) │
                     │  • Relational DB: PostgreSQL (Sessions & History)  │
                     │  • Embeddings: BAAI/bge-base-en-v1.5               │
                     │  • Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2  │
                     │  • LLMs: Gemini 2.5 Flash / Groq LLMs              │
                     └─────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 1. 🤖 AI UPSC Mentor & Advanced RAG
* **Multi-Mode Routing**: Dedicated handlers for **Prelims (Static concepts)**, **Mains (Structured analytical answers)**, and **Current Affairs**.
* **Dual PDF Ingestion**:
  * **Docling Layout Parser** for digital PDFs with multi-column table and reading-order reconstruction.
  * **Gemini Multimodal VLM** for handwritten, scanned, and diagram-heavy notes.
* **Semantic Vector Search & Reranking**: Combines dense vector retrieval in Qdrant with `ms-marco-MiniLM-L-6-v2` cross-encoder reranking for ultra-high precision context retrieval.
* **Conversational Memory**: Multi-turn history stored in PostgreSQL with intelligent query condensation.
* **Token Streaming**: Real-time Server-Sent Events (SSE) streaming at `/api/v1/query/stream`.

### 2. 📰 Automated Daily News & Current Affairs
* **Automated Scrapers**: Auto-collects daily editorial and policy updates from *The Hindu*, *PIB*, and *Indian Express*.
* **Multiple Output Formats**:
  * **3-Bullet Summaries**: High-yield executive summaries.
  * **Mains Analysis**: Issue $\rightarrow$ Pros/Cons $\rightarrow$ Way Forward.
  * **Daily Prelims MCQs**: Test knowledge directly from the day's events.
* **Clickable Source Citations**: Verified direct links to official government releases and newspapers.

### 3. 📝 Interactive MCQ Practice
* Practice by subject (**History, Geography, Polity, Economy, Environment, Current Affairs**).
* Immediate explanation and syllabus paper mapping (GS1, GS2, GS3, GS4).

### 4. 🎨 Modern Glassmorphic Web UI
* Built with **React 18, Vite, Tailwind CSS, Framer Motion**, and **Lucide Icons**.
* Dark/Light mode, OTP login mock flow, subject dashboard, sidebar drawer, and responsive mobile layout.

### 5. 🛠️ Admin Management Portal
* Document upload interface (drag-and-drop PDF ingestion).
* Real-time cache telemetry, collection indexing status, and scraper pipeline controls.

---

## 📁 Repository Structure

```
.
├── admin_page/                     # Admin Portal (HTML/JS/CSS & Vite bundle)
├── app/                            # Core FastAPI Backend
│   ├── api/routes/                 # REST & SSE API Route Controllers
│   │   ├── admin.py                # Admin document uploads & system metrics
│   │   ├── documents.py            # Docling digital PDF ingestion
│   │   ├── extract_page.py         # Gemini VLM scanned document ingestion
│   │   ├── mcq.py                  # MCQ practice generation & validation
│   │   ├── news.py                 # Daily news feeds and article queries
│   │   ├── query.py                # Standard RAG query endpoint
│   │   └── query_stream.py         # SSE token-streaming query endpoint
│   ├── core/                       # App settings, DB connections, SQLite cache
│   ├── database/                   # PostgreSQL schemas & SQLAlchemy repository
│   ├── retrieval/                  # Vector search, reranker, query classifier, prompts
│   └── services/                   # Embeddings, Qdrant client, news scraper service
├── docs/                           # Architectural diagrams and evaluation reports
├── extraction/                     # PDF extraction scripts & layout helpers
├── frontend/                       # React 18 + Vite + Tailwind Frontend Application
│   ├── public/                     # Static icons & assets
│   └── src/
│       ├── components/             # Layout, Navbar, Dashboard, Chat, MCQ, News, Admin
│       ├── context/                # App state & user auth context
│       └── pages/                  # Home, Login, MainFlow, Notebook, UPSCPlatform
├── pipeline/                       # Daily news scraper, scheduler & backfill scripts
├── preprocessing/                  # Chunking strategies & text normalizers
├── requirements/                   # Modular Python requirements (api, extraction, etc.)
├── scripts/                        # Evaluation, batch extract & ingestion utilities
├── tests/                          # 50+ unit and integration tests
├── docker-compose.yml              # PostgreSQL + Qdrant container orchestration
├── HOW_TO_RUN.md                   # Step-by-step run instructions
├── start_dev.bat                   # 1-Click development launcher for Windows
└── README.md                       # Main documentation
```

---

## ⚡ Quick Start Guide

### Prerequisites
* **Node.js** (v18+)
* **Python** (v3.10+)
* **Docker Desktop** (for PostgreSQL & Qdrant)

---

### 1. Start Database Containers
```powershell
docker-compose up -d
```
* **PostgreSQL**: `localhost:5432`
* **Qdrant Vector DB**: `localhost:6333`

---

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
# Database & Vector DB
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/upsc_rag
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedding & Reranker Models
EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2

# LLM Providers (Configure at least one)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

---

### 3. One-Click Launch (Windows)
Double-click [`start_dev.bat`](file:///c:/Users/vishn/Downloads/RAG-main/RAG-main/start_dev.bat) or run from terminal:
```powershell
.\start_dev.bat
```
* Automatically clears ports `8000` & `5173`
* Launches the **FastAPI Backend** on `http://localhost:8000`
* Launches the **React Frontend** on `http://localhost:5173`
* Opens the application in your default browser

---

### 4. Manual Launch (Step-by-Step)

#### Terminal 1 — Backend
```bash
pip install -r requirements/api.txt
uvicorn app.main:app --reload --port 8000
```

#### Terminal 2 — Frontend
```bash
cd frontend
npm install
npm run dev
```

#### Access Links:
* **Frontend Web App**: [http://localhost:5173](http://localhost:5173)
* **Interactive API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🚀 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Standard RAG question answering with citations & memory |
| `POST` | `/api/v1/query/stream` | Server-Sent Events (SSE) real-time streaming answer |
| `GET`  | `/api/v1/news/daily` | Fetch today's curated UPSC current affairs articles |
| `POST` | `/api/v1/news/scrape` | Trigger manual news scraper cycle |
| `POST` | `/api/v1/mcq/generate` | Generate Prelims MCQs for a given topic or news item |
| `POST` | `/api/v1/documents` | Upload and index digital PDFs using Docling |
| `POST` | `/api/v2/documents` | Upload and index scanned PDFs using Gemini VLM |
| `GET`  | `/api/v1/admin/stats` | System telemetry, cache stats, and collection metrics |

---

## 🧪 Running Automated Tests

Run the full automated test suite:
```powershell
pytest tests/ -v
```

---

## 📄 License
This project is licensed under the MIT License.
