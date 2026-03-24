"""
rag.py — Core RAG pipeline for RAG (Retrieval-Augmented Generation)
handles: Document ingestion, chunking, embedding, vector storage, retrieval,
and augmented generation via a swappable LLM provider.

Supported providers (set LLM_PROVIDER in .env):
  - "ollama"    → local Ollama server (default, free, private)
  - "openai"    → OpenAI API (gpt-4o, gpt-3.5-turbo, etc.)
  - "anthropic" → Anthropic API (claude-sonnet-4-6, etc.)
"""

# BUG FIX 1 — removed these 3 bad imports that were here:
#   from curses import meta         ← curses is Unix-only, crashes on Windows
#   from math import dist           ← shadows the 'dist' variable in retrieve_context()
#   from annotated_types import doc ← shadows the 'doc' variable in retrieve_context()

import os
import uuid
from pathlib import Path
from typing import Generator

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter


# --- Config and Setup ---

LLM_PROVIDER      = os.getenv("LLM_PROVIDER",      "ollama")
LLM_MODEL         = os.getenv("LLM_MODEL",          "llama3")
OLLAMA_HOST       = os.getenv("OLLAMA_HOST",        "http://localhost:11434")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",     "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY",  "")

EMBED_MODEL    = os.getenv("EMBED_MODEL",    "nomic-embed-text")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_store")
COLLECTION     = "documents"

CHUNK_SIZE    = 512   # characters per chunk — tune for your docs
CHUNK_OVERLAP = 64    # overlap preserves context across chunk boundaries
TOP_K         = 5     # number of chunks retrieved per query

SYSTEM_PROMPT = """\
You are a helpful document assistant. Answer the user's question using ONLY
the context excerpts provided below. If the answer is not contained in the
context, say so honestly — do not make things up.
Always cite the source file name when referencing specific information.
"""


# --- ChromaDB Setup — lazy singleton ---

_collection = None


def _get_collection() -> chromadb.Collection:
    """Lazily initialize and return the persistent ChromaDB
    collection for storing document chunks and embeddings."""

    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        embed_fn = embedding_functions.OllamaEmbeddingFunction(
            url=f"{OLLAMA_HOST}/api/embeddings",
            model_name=EMBED_MODEL,
        )
        _collection = client.get_or_create_collection(
            name="documents",
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# --- Document Processing / Parsing ---

def _parse_file(file_path: Path) -> str:
    """
    Extracts plain text from uploaded file.
    Supports: PDF, DOCX, TXT, and Markdown.
    Imports are lazy (inside the function) to keep startup fast.
    """

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


# --- Ingestion Pipeline ---

def ingest_document(file_path: Path, source_name: str) -> dict:
    """
    Full ingestion pipeline for one document:
    Parse -> split into chunks -> embed via Ollama -> store in ChromaDB

    Returns a summary dict: {source, chunks, total_chars}
    """

    # Step 1: Extract raw text
    raw_text = _parse_file(file_path)
    if not raw_text.strip():
        raise ValueError("Document appears to be empty or unreadable.")

    # Step 2: Split into overlapping chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(raw_text)

    # Step 3: Store in ChromaDB (embedding happens automatically via embed_fn)
    col = _get_collection()
    col.add(
        documents=chunks,
        ids=[str(uuid.uuid4()) for _ in chunks],
        metadatas=[
            {"source": source_name, "chunk_index": i}
            for i, _ in enumerate(chunks)
        ],
    )

    return {
        "source":      source_name,
        "chunks":      len(chunks),    # BUG FIX 2 — was "num_chunks", must be "chunks"
        "total_chars": len(raw_text),
    }


# --- Retrieval (semantic search) ---

def retrieve_context(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embeds the query and retrieves the top-k most semantically similar
    chunks from ChromaDB using cosine similarity.

    Returns list of: {text, source, chunk_index, distance}
    Lower distance = more relevant.
    """

    results = _get_collection().query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],  # BUG FIX 3 — had a leading space: " distances"
    )

    return [
        {
            "text":        doc,
            "source":      meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index", 0),
            "distance":    round(dist, 4),
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


# --- LLM Provider Abstraction Layer ---

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
    """Stream tokens from the OpenAI API (gpt-4o, gpt-3.5-turbo, etc.)"""
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
    """Stream tokens from the Anthropic API (claude-sonnet-4-6, etc.)"""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    with client.messages.stream(
        model=LLM_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        yield from stream.text_stream


# Provider registry — switching providers is a one-line .env change
_PROVIDERS = {
    "ollama":    _stream_ollama,
    "openai":    _stream_openai,
    "anthropic": _stream_anthropic,
}


# --- Augmented Generation Pipeline ---

def _build_prompt(query: str, context_chunks: list[dict]) -> str:
    """Builds the user message with retrieved context injected."""

    context = "\n\n---\n\n".join(
        f"[Source: {c['source']}, chunk {c['chunk_index']}]\n{c['text']}"  # BUG FIX 4 — was missing opening [
        for c in context_chunks
    )
    return f"{context}\n\nQuestion: {query}"


def stream_answer(query: str) -> Generator[str, None, None]:
    """
    Full RAG query pipeline — streams LLM response tokens.
      1. Retrieve top-k relevant chunks from ChromaDB
      2. Build augmented prompt with retrieved context
      3. Stream response via the configured LLM provider
    """

    chunks = retrieve_context(query)

    if not chunks:
        yield "No documents found in the vector store. Please upload a document first."
        return

    provider_fn = _PROVIDERS.get(LLM_PROVIDER)
    if provider_fn is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            f"Choose from: {list(_PROVIDERS.keys())}"
        )

    yield from provider_fn(SYSTEM_PROMPT, _build_prompt(query, chunks))


# --- Utility Helpers ---

def list_sources() -> list[str]:
    """Returns a sorted, deduplicated list of all ingested source file names."""
    results = _get_collection().get(include=["metadatas"])
    return sorted({m.get("source", "unknown") for m in results["metadatas"]})


def delete_source(source_name: str) -> int:
    """
    Deletes all chunks belonging to a source from ChromaDB.
    Returns the number of chunks deleted.
    """
    col     = _get_collection()
    results = col.get(where={"source": source_name}, include=["metadatas"])
    if results["ids"]:
        col.delete(ids=results["ids"])
    return len(results["ids"])