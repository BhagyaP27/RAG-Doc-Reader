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

