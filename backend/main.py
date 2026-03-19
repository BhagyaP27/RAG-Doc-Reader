"""
main.py — FastAPI Server
========================
The HTTP layer that sits between the React frontend and the RAG pipeline.
 
Routes:
  GET  /health              — liveness check
  POST /ingest              — upload + index a document
  POST /query               — ask a question (streams SSE tokens)
  GET  /sources             — list all indexed documents
  DELETE /sources/{name}    — remove a document from the vector store
 
Run with:
  python main.py
  → http://localhost:8000
  → http://localhost:8000/docs  (interactive Swagger UI — great for testing)

"""

import shutil
import tempfile
from pathlib import Path
 
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
 
from rag import delete_source, ingest_document, list_sources, stream_answer
 
# Load .env file into environment variables before anything else
load_dotenv()


#--- App setup ---

app = FastAPI(
    title="RAG DOC reader API",
    description="A simple FastAPI backend for a Retrieval-Augmented Generation (RAG) document reader application.",
    version="1.0",
)

# CORS — allow the React dev server (Vite runs on 5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".docx"}