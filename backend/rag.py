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
from langchain_text_splitter import RecursiveCharacterTextSplitter


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

