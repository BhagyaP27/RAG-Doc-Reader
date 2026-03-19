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


#--- Request / response schemas (pydantic validates these automatically) ---

class QueryRequest(BaseModel):
    question: str


#--_ routes ---

@app.get("/health")
async def health():
    """Quick check that the server is up. Frontend polls this on startup."""
    return {"status": "ok"}
 
 
@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    """
    Accepts a file upload, saves it to a temp file, runs the full
    ingestion pipeline (parse → chunk → embed → store), then cleans up.
    Returns: {message, source, chunks, total_chars}
    """
    # Validate file type
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{suffix}' not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
 
    # Save upload to a temp file so parsers (pypdf, python-docx) can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
 
    try:
        result = ingest_document(tmp_path, source_name=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)  # always clean up the temp file
 
    return {
        "message": f"Successfully ingested '{file.filename}'",
        **result,
    }
 
 
@app.post("/query")
async def query(body: QueryRequest):
    """
    Runs the full RAG query pipeline and streams the LLM response
    as Server-Sent Events (SSE).
 
    The React frontend reads this stream with the Fetch ReadableStream API,
    appending each token to the answer as it arrives — no waiting for the
    full response.
 
    SSE format:
      data: <token>\\n\\n
      data: [DONE]\\n\\n   ← signals end of stream
    """
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
 
    def token_generator():
        for token in stream_answer(body.question):
            # Escape newlines so the SSE line format stays valid
            safe_token = token.replace("\n", "<br>")
            yield f"data: {safe_token}\n\n"
        yield "data: [DONE]\n\n"
 
    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",   # prevents Nginx from buffering the stream
        },
    )
 
 
@app.get("/sources")
async def sources():
    """Returns all document names currently stored in the vector DB."""
    return {"sources": list_sources()}
 
 
@app.delete("/sources/{source_name}")
async def delete(source_name: str):
    """
    Removes all vector chunks for a given source file.
    Returns the number of chunks deleted.
    """
    count = delete_source(source_name)
    if count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Source '{source_name}' not found in vector store.",
        )
    return {
        "message":        f"Deleted '{source_name}' from vector store.",
        "deleted_chunks": count,
    }
 