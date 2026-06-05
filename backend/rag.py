"""
rag.py — Core RAG pipeline
Switched from ChromaDB to FAISS because ChromaDB's dependency
chroma-hnswlib has no Windows wheel for Python 3.13.

FAISS is faster, simpler, and works on any Python version.
We persist vectors + metadata manually to disk as .npy + .json files.

Supported LLM providers (set LLM_PROVIDER in .env):
  - "ollama"    → local Ollama server (default)
  - "openai"    → OpenAI API
  - "anthropic" → Anthropic API
"""

import json
import os
import uuid
from pathlib import Path
from typing import Generator

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LLM_PROVIDER      = os.getenv("LLM_PROVIDER",      "ollama")
LLM_MODEL         = os.getenv("LLM_MODEL",          "llama3")
OLLAMA_HOST       = os.getenv("OLLAMA_HOST",        "http://localhost:11434")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",     "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY",  "")

VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_store")
EMBED_MODEL    = "all-MiniLM-L6-v2"   # lightweight, fast, runs fully offline

CHUNK_SIZE    = 512
CHUNK_OVERLAP = 64
TOP_K         = 5

SYSTEM_PROMPT = """\
You are a helpful document assistant. Answer the user's question using ONLY
the context excerpts provided below. If the answer is not contained in the
context, say so honestly — do not make things up.
Always cite the source file name when referencing specific information.
"""

# File paths for persistence
_DB_DIR      = Path(VECTOR_DB_PATH)
_INDEX_FILE  = _DB_DIR / "index.faiss"
_META_FILE   = _DB_DIR / "metadata.json"


# ---------------------------------------------------------------------------
# Embedding model — lazy singleton
# ---------------------------------------------------------------------------
_embedder: SentenceTransformer | None = None

def _get_embedder() -> SentenceTransformer:
    """Load the sentence transformer model once and reuse it."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _embed(texts: list[str]) -> np.ndarray:
    """Convert a list of strings to a float32 numpy array of embeddings."""
    embedder = _get_embedder()
    vecs = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return vecs.astype("float32")


# ---------------------------------------------------------------------------
# FAISS index + metadata — lazy load / create
# ---------------------------------------------------------------------------
_index: faiss.Index | None = None
_metadata: list[dict]      = []   # parallel list: _metadata[i] matches vector i in _index


def _load_store():
    """Load the FAISS index and metadata from disk if they exist."""
    global _index, _metadata
    _DB_DIR.mkdir(parents=True, exist_ok=True)

    if _INDEX_FILE.exists() and _META_FILE.exists():
        _index    = faiss.read_index(str(_INDEX_FILE))
        _metadata = json.loads(_META_FILE.read_text(encoding="utf-8"))
    else:
        # 384 = embedding dimension for all-MiniLM-L6-v2
        _index    = faiss.IndexFlatIP(384)   # Inner Product = cosine sim on normalised vecs
        _metadata = []


def _save_store():
    """Persist the FAISS index and metadata to disk."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(_index, str(_INDEX_FILE))
    _META_FILE.write_text(json.dumps(_metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_store():
    """Return (index, metadata), loading from disk on first call."""
    global _index, _metadata
    if _index is None:
        _load_store()
    return _index, _metadata


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------
def _parse_file(file_path: Path) -> str:
    """Extract plain text from PDF, DOCX, TXT, or Markdown."""
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix == ".docx":
        from docx import Document 
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)

    if suffix in (".txt", ".md", ".markdown"):
        return file_path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {suffix}")


# ---------------------------------------------------------------------------
# Ingestion pipeline
# ---------------------------------------------------------------------------
def ingest_document(file_path: Path, source_name: str) -> dict:
    """
    Full ingestion pipeline:
    Parse → chunk → embed (sentence-transformers) → store in FAISS
    """
    raw_text = _parse_file(file_path)
    if not raw_text.strip():
        raise ValueError("Document appears to be empty or unreadable.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(raw_text)

    # Embed all chunks at once (batched — much faster than one by one)
    vecs = _embed(chunks)

    # Normalise vectors so inner product == cosine similarity
    faiss.normalize_L2(vecs)

    index, metadata = _get_store()

    # Add vectors to FAISS
    index.add(vecs)

    # Add matching metadata entries
    for i, chunk_text in enumerate(chunks):
        metadata.append({
            "id":          str(uuid.uuid4()),
            "source":      source_name,
            "chunk_index": i,
            "text":        chunk_text,
        })

    _save_store()

    return {
        "source":      source_name,
        "chunks":      len(chunks),
        "total_chars": len(raw_text),
    }


# ---------------------------------------------------------------------------
# Retrieval — semantic search
# ---------------------------------------------------------------------------
def retrieve_context(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embed the query, search FAISS for the top-k nearest vectors,
    and return the matching chunk metadata.
    """
    index, metadata = _get_store()

    if index.ntotal == 0:
        return []

    # Embed and normalise the query
    query_vec = _embed([query])
    faiss.normalize_L2(query_vec)

    # Search — returns distances and indices of top-k results
    k         = min(top_k, index.ntotal)
    distances, indices = index.search(query_vec, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:   # FAISS returns -1 for empty slots
            continue
        meta = metadata[idx]
        results.append({
            "text":        meta["text"],
            "source":      meta["source"],
            "chunk_index": meta["chunk_index"],
            "distance":    round(float(dist), 4),
        })

    return results


# ---------------------------------------------------------------------------
# LLM provider abstraction
# ---------------------------------------------------------------------------
def _stream_ollama(system: str, user: str) -> Generator[str, None, None]:
    """Stream tokens from a local Ollama model."""
    import ollama as ol
    client = ol.Client(host=OLLAMA_HOST)
    for chunk in client.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        stream=True,
    ):
        token = chunk["message"]["content"]
        if token:
            yield token


def _stream_openai(system: str, user: str) -> Generator[str, None, None]:
    """Stream tokens from the OpenAI API."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        stream=True,
    ) as stream:
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token


def _stream_anthropic(system: str, user: str) -> Generator[str, None, None]:
    """Stream tokens from the Anthropic API."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    with client.messages.stream(
        model=LLM_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        yield from stream.text_stream


_PROVIDERS = {
    "ollama":    _stream_ollama,
    "openai":    _stream_openai,
    "anthropic": _stream_anthropic,
}


# ---------------------------------------------------------------------------
# Augmented generation
# ---------------------------------------------------------------------------
def _build_prompt(query: str, context_chunks: list[dict]) -> str:
    """Build the user message with retrieved context injected."""
    context = "\n\n---\n\n".join(
        f"[Source: {c['source']}, chunk {c['chunk_index']}]\n{c['text']}"
        for c in context_chunks
    )
    return f"{context}\n\nQuestion: {query}"


def stream_answer(query: str) -> Generator[str, None, None]:
    """
    Full RAG query pipeline — streams LLM response tokens.
      1. Retrieve top-k relevant chunks from FAISS
      2. Build augmented prompt with context injected
      3. Stream response via the configured LLM provider
    """
    chunks = retrieve_context(query)

    if not chunks:
        yield "No documents found. Please upload a document first."
        return

    provider_fn = _PROVIDERS.get(LLM_PROVIDER)
    if provider_fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            f"Choose from: {list(_PROVIDERS.keys())}"
        )

    yield from provider_fn(SYSTEM_PROMPT, _build_prompt(query, chunks))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def list_sources() -> list[str]:
    """Return a sorted, deduplicated list of all ingested source file names."""
    _, metadata = _get_store()
    return sorted({m["source"] for m in metadata})


def delete_source(source_name: str) -> int:
    """
    Remove all chunks belonging to a source.
    FAISS doesn't support deletion, so we rebuild the index without those entries.
    Returns the number of chunks deleted.
    """
    global _index, _metadata

    index, metadata = _get_store()

    # Split into keep and delete
    keep    = [m for m in metadata if m["source"] != source_name]
    removed = len(metadata) - len(keep)

    if removed == 0:
        return 0

    # Rebuild FAISS index from the kept chunks only
    new_index = faiss.IndexFlatIP(384)

    if keep:
        texts = [m["text"] for m in keep]
        vecs  = _embed(texts)
        faiss.normalize_L2(vecs)
        new_index.add(vecs)

    _index    = new_index
    _metadata = keep
    _save_store()

    return removed