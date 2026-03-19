"""
eval_rag.py — RAG Quality Evaluator
=====================================
Measures how much RAG improves answer faithfulness vs a bare LLM baseline.
This generates the stat for your portfolio: "improved faithfulness by X%"
 
Usage:
  python eval_rag.py --doc path/to/your.pdf
  python eval_rag.py --doc your.pdf --questions my_questions.json
 
Output:
  - Side-by-side answers: RAG vs no-context baseline
  - Faithfulness score per answer (word-overlap heuristic)
  - Final summary + portfolio stat
  - Saves full results to eval_results.json
"""

import argparse
import json
import os
import time
from pathlib import Path

from rag import _build_prompt, ingest_document, retrieve_context, stream_answer


#--- Default sample Questions (change later to test specific question dependant on users documemts) bare bones structure

DEFAULT_QUESTIONS = [
    {"question": "What is the main topic or purpose of this document?"},
    {"question": "What are the key findings, conclusions, or recommendations?"},
    {"question": "What technologies, methods, or tools are mentioned?"},
    {"question": "Who is the intended audience for this document?"},
    {"question": "What problem does this document describe or try to solve?"},
]


# -- Helpers----

def collect_stream(gen) -> str:
    """Drain a generator into a single string."""
    return "".join(gen)
 
 
def score_faithfulness(answer: str, context_chunks: list[dict]) -> float:
    """
    Simple faithfulness heuristic: what fraction of sentences in the answer
    contain words that appear in the retrieved context?
 
    A 'proper' eval uses an LLM-as-judge — this is fast and dependency-free,
    which makes it suitable for a portfolio demo. It's directionally accurate.
    """
    if not context_chunks:
        return 0.0
 
    context_words = set(
        " ".join(c["text"] for c in context_chunks).lower().split()
    )
    sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 10]
    if not sentences:
        return 0.0
 
    grounded = sum(
        1 for s in sentences
        if len(set(s.lower().split()) & context_words) / max(len(s.split()), 1) > 0.30
    )
    return round(grounded / len(sentences), 3)
 
 
def get_bare_answer(question: str) -> str:
    """
    Get an LLM answer with NO retrieved context injected.
    This is the baseline that shows what the model does without RAG.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model    = os.getenv("LLM_MODEL", "llama3")
    host     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
 
    if provider == "ollama":
        import ollama as ol
        chunks = ol.Client(host=host).chat(
            model=model,
            messages=[{"role": "user", "content": question}],
            stream=True,
        )
        return "".join(c["message"]["content"] for c in chunks)
 
    if provider == "openai":
        from openai import OpenAI
        r = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).chat.completions.create(
            model=model, messages=[{"role": "user", "content": question}]
        )
        return r.choices[0].message.content
 
    if provider == "anthropic":
        import anthropic
        m = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
            model=model, max_tokens=512,
            messages=[{"role": "user", "content": question}],
        )
        return m.content[0].text
 
    return "[unsupported provider]"
 