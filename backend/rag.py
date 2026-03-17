"""
this file - Core RAF pipeline for RAG (Retrieval-Augmented Generation)
handles: Document injestion, chuncking, embedding, vector storage, retieval,
and augmented generation via a swappable LLM provider.

Supported providers (set LLM_PROVIDER in .env):

"""

import os
import uuid
from pathlib import Path
from typing import Generator

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter


#--- Config and Setup ---

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL         = os.getenv("LLM_MODEL", "llama3")
OLLAMA_HOST       = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
 
EMBED_MODEL    = os.getenv("EMBED_MODEL", "nomic-embed-text")
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


#--- Chromadb Setup ---

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
            metadata={"hnsw:space": "cosine"},  # cosine similarity scoring
        )
    return _collection


#--- Document Processing/parsing ---

def _parse_file(file_path: Path) -> str:
    """
    Extracts plain text from uploaded file.
    Supports: PDF, DOCX, TXT, and Markdown 
    Imports are lazy (inside the function) to keep startup fast and dependencies minimal.
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



#-- Ingestion Pipeline ---

def ingest_document(file_path: Path, source_name: str) -> dict:
    """
    Full ingestion pipeline: parse, chunk, embed, and store document in vector DB.
    for one document. Parse-> split into chunks -> embed via Ollama -> store in ChromaDB

    Returns a summary dict: {
        "source": source_name,
        "num_chunks": int,
        "status": "success" or "error",
        "error": str (if any)
    }
    """

    #step 1 Extract raw text from file

    raw_text = _parse_file(file_path)
    if not raw_text.strip():
        raise ValueError("No extractable text found in document. DOcument appears to be empty or unreadable")
    
    #step 2: split into overlapping chunks
    # use RecursiveCharacterTextSplitter tries to break at paragraph/sentence
    # Boundaries rather than cutting mid-sentence, producing cleaner chunks

    #setting up the text splitter with our defined chunk size, overlap, and preferred separators
    splitter = RecursiveCharacterTextSplitter(
        chunk_size= CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""],
    )

    chunks = splitter.split_text(raw_text)

    #step 3: Store in ChromaDB (embedding happens automatically via embed_fn)

    col = _get_collection()
    col.add(
        documents=chunks,
        ids=[str(uuid.uuid4()) for _ in chunks],  # unique ID for each chunk
        metadatas=[
            {"source": source_name, "chunk_index": i}
            for i, _ in enumerate(chunks)
        ],
    )


    return {
        "source": source_name,
        "num_chunks": len(chunks),
        "total_chars": len(raw_text),        
        "status": "success",
        "error": None,
    }


#___ Retrieval (semantic search) ___

