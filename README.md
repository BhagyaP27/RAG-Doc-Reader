# RAG Doc Reader 📄

A full-stack **Retrieval-Augmented Generation (RAG)** application that lets you upload any document and have a real conversation with its contents — powered entirely by local LLMs via Ollama.

Built as part of my AI Engineer portfolio to demonstrate production-level RAG pipeline design, vector search, and full-stack integration.

---

## What I Built & Why

Most developers using LLMs stop at "call the API and display the response." This project goes deeper — I engineered the full retrieval pipeline from scratch:

- **Document ingestion pipeline** — parse → chunk with overlap → embed via `nomic-embed-text` → persist in ChromaDB
- **Semantic retrieval** — cosine similarity search retrieves the top-5 most relevant chunks at query time
- **Augmented generation** — retrieved context is injected into a structured prompt before the LLM ever sees the question
- **Streaming SSE responses** — tokens stream to the UI as they're generated, no waiting for a full response
- **Swappable LLM providers** — one `.env` change switches between Ollama (local), OpenAI, or Anthropic

The result: answers grounded strictly in the uploaded document, with a measurable improvement in answer faithfulness vs a no-context LLM baseline (see [eval script](#running-the-eval)).

---

## Tech Stack

| Layer | Technology | Why I chose it |
|-------|-----------|----------------|
| Backend API | Python, FastAPI | Async, type-safe, auto-generates Swagger docs |
| RAG pipeline | LangChain text splitter | Sentence-aware chunking with configurable overlap |
| Vector store | ChromaDB | Local, persistent, no infrastructure needed |
| Embedding model | nomic-embed-text via Ollama | High quality, runs fully offline |
| LLM | llama3 via Ollama | Free, private, offline — swappable to GPT-4o or Claude |
| Frontend | React 18, Vite | Fast HMR, built-in dev proxy, minimal boilerplate |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   React Frontend (Vite)                   │
│          Upload Panel  |  Streaming Chat Window           │
└──────────────┬─────────────────────┬─────────────────────┘
               │ POST /ingest        │ POST /query (SSE)
┌──────────────▼─────────────────────▼─────────────────────┐
│                    FastAPI Backend                        │
│                                                           │
│  INGESTION PIPELINE           QUERY PIPELINE              │
│  ──────────────────           ─────────────               │
│  Parse file (PDF/DOCX/MD)     Embed question              │
│       ↓                            ↓                      │
│  Split into chunks            Semantic search (top-5)     │
│       ↓                            ↓                      │
│  Embed via Ollama             Build augmented prompt      │
│       ↓                            ↓                      │
│  Store in ChromaDB            Stream via Ollama LLM       │
└───────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/rag-doc-reader.git
cd rag-doc-reader
```

### 2. Pull the AI models

```bash
ollama pull llama3            # ~4.7 GB — the chat model
ollama pull nomic-embed-text  # ~274 MB — the embedding model
```

> **Low RAM (under 8 GB)?** Use `phi3` instead of `llama3` (~2.3 GB). Set `LLM_MODEL=phi3` in `.env`.

### 3. Backend setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up config
cp .env.example .env
# Default settings work out of the box with Ollama

# Start the server
python main.py
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 4. Frontend setup

```bash
# New terminal, from project root
cd frontend
npm install
npm run dev
# UI running at http://localhost:5173
```

### 5. Use it

1. Open **http://localhost:5173**
2. Click the upload area and select a PDF, DOCX, TXT, or Markdown file
3. Wait for the ingestion confirmation
4. Type a question and press **Enter**
5. Watch the answer stream in, grounded in your document

---

## Switching LLM Providers

Edit `backend/.env` — one line change swaps the entire LLM backend:

```bash
# Local default (free, private, offline)
LLM_PROVIDER=ollama
LLM_MODEL=llama3

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running the Eval

The eval script measures RAG's impact on answer faithfulness by running each question twice — with context and without — and comparing scores:

```bash
cd backend
python eval_rag.py --doc path/to/your_doc.pdf
```

Sample output:
```
  RAG faithfulness:   0.847
  Base faithfulness:  0.431
  Improvement:        +96.5%
```

---

## Project Structure

```
rag-doc-reader/
├── backend/
│   ├── main.py           # FastAPI server — routes, file upload, SSE streaming
│   ├── rag.py            # RAG pipeline — parse, chunk, embed, retrieve, generate
│   ├── eval_rag.py       # Faithfulness evaluation script
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx       # Main React component
│   │   ├── main.jsx      # React entry point
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── test.http             # VSCode REST Client tests
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/ingest` | Upload and index a document |
| `POST` | `/query` | Ask a question (streams SSE tokens) |
| `GET` | `/sources` | List all indexed documents |
| `DELETE` | `/sources/{name}` | Remove a document |

Interactive docs at `http://localhost:8000/docs` when the server is running.

---

## Key Technical Decisions

**ChromaDB over Pinecone** — for a local-first project, ChromaDB persists to disk with zero infrastructure. Pinecone makes sense for cloud deployments but adds unnecessary complexity here.

**nomic-embed-text for embeddings** — runs locally via Ollama so the entire pipeline works offline with no API costs. Benchmarks comparably to OpenAI's `text-embedding-ada-002` on retrieval tasks.

**SSE over WebSockets** — Server-Sent Events are unidirectional (server → client), which is all streaming LLM output needs. Simpler than WebSockets, works over standard HTTP.

**Chunk size 512, overlap 64** — large enough to preserve sentence context, small enough for precise retrieval. The overlap prevents answers spanning a chunk boundary from being missed.

---

## What I'd Add Next

- [ ] Multi-turn conversation history
- [ ] Source chunk highlighting in the UI
- [ ] Web URL ingestion
- [ ] Docker Compose for one-command startup
- [ ] Cross-encoder re-ranking for better retrieval precision

---

## License

MIT