# RAG Doc Reader

A full-stack AI-powered document assistant. Upload any PDF, Word doc, or Markdown file and have a real conversation with its contents — powered entirely by local LLMs running on your own machine via Ollama.

No API keys. No cloud. No data leaving your computer.

---

## Features

- Upload PDF, DOCX, TXT, and Markdown files
- Documents are chunked, embedded, and stored in a local FAISS vector database
- Ask questions in natural language — semantic search finds the most relevant passages
- Answers stream token by token in real time, grounded strictly in your document
- Light and dark mode with a custom blue colour palette
- Swap between Ollama (local), OpenAI, and Anthropic with a single config change

---

## How it works

```
Upload a file
    ↓
Parse text → split into chunks → embed with sentence-transformers → store in FAISS
                                                                          ↓
Ask a question → embed question → semantic search → retrieve top 5 chunks
                                                                          ↓
                                        Inject chunks into prompt → stream answer via Ollama
```

This pattern is called **Retrieval-Augmented Generation (RAG)**. The LLM only sees the chunks most relevant to your question, which keeps answers grounded and reduces hallucination.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| RAG pipeline | LangChain text splitter, FAISS, sentence-transformers |
| Embedding model | all-MiniLM-L6-v2 (runs fully offline) |
| LLM | Ollama — llama3, phi3, mistral (swappable) |
| Frontend | React 18, Vite |

---

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- [Ollama](https://ollama.com) installed

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/rag-doc-reader.git
cd rag-doc-reader
```

### 2. Pull the Ollama model

```bash
ollama pull llama3
```

> Low RAM (under 8 GB)? Use `phi3` instead — it's 2.3 GB and works great for document Q&A. Update `LLM_MODEL=phi3` in `backend/.env`.

### 3. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up config
cp env.example.txt .env

# Start the server
python main.py
```

Backend runs at `http://localhost:8000`
Interactive API docs at `http://localhost:8000/docs`

### 4. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## Running the app

Every time you come back to the project, open three terminals:

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Backend
cd backend
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
python main.py

# Terminal 3 — Frontend
cd frontend
npm run dev
```

Then open `http://localhost:5173` in your browser.

---

## Usage

1. Open `http://localhost:5173`
2. Click the upload area in the sidebar and select a file
3. Wait for the ingestion confirmation — this indexes the document
4. Type a question in the input bar and press **Enter**
5. The answer streams in, grounded in your document

> The first upload is slightly slower — the embedding model (`all-MiniLM-L6-v2`) downloads automatically on first use (~90 MB) and is cached after that.

---

## Switching LLM providers

Edit `backend/.env`:

```bash
# Local — default, free, private
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

## Running the eval

Measures how much RAG improves answer quality vs a bare LLM with no context:

```bash
cd backend
python eval_rag.py --doc path/to/your_doc.pdf
```

Output:
```
  RAG faithfulness:   0.847
  Base faithfulness:  0.431
  Improvement:        +96.5%
```

---

## Project structure

```
rag-doc-reader/
├── backend/
│   ├── main.py           # FastAPI server — all API routes
│   ├── rag.py            # RAG pipeline — parse, embed, retrieve, generate
│   ├── eval_rag.py       # Evaluation script
│   ├── requirements.txt
│   └── env.example.txt   # Copy to .env and configure
├── frontend/
│   ├── src/
│   │   ├── App.jsx       # Main UI component
│   │   ├── main.jsx      # React entry point
│   │   └── index.css     # Global styles + CSS variables
│   ├── index.html
│   ├── package.json
│   └── vite.config.js    # Dev server + API proxy config
├── test.http             # VSCode REST Client test file
└── README.md
```

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server liveness check |
| `POST` | `/ingest` | Upload and index a document |
| `POST` | `/query` | Ask a question — streams SSE tokens |
| `GET` | `/sources` | List all indexed documents |
| `DELETE` | `/sources/{name}` | Remove a document |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Blank white page | Check browser console for errors — likely a JS crash in App.jsx |
| Upload fails | Make sure `python main.py` is running in Terminal 2 |
| `No module named X` | Virtual environment not active — run `venv\Scripts\activate` first |
| Slow first answer | llama3 takes 10–15s to warm up on the first query — normal |
| `ollama: connection refused` | Run `ollama serve` in Terminal 1 |

---

## What I'd add next

- Multi-turn conversation history
- Source chunk highlighting — show which passages were used
- Ingest from a URL instead of just file upload
- Docker Compose for one-command startup
- Re-ranking with a cross-encoder model for better retrieval precision

---

## License

MIT