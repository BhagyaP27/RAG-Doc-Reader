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
 

 #-- Evaluation loop----

def run_eval(questions: list[dict], verbose: bool = True) -> dict:
    """
    For each question:
      1. Get the RAG answer + retrieved context
      2. Get the bare LLM answer with no context
      3. Score faithfulness of the RAG answer vs the retrieved chunks
    """
    results = []
    total_rag = total_base = 0.0

    for i,q in enumerate(questions,1):
        question = q["question"]
        print(f"\n{'='*60}")
        print(f"Q{i}: {question}")
        print("-" * 60)
 
        # RAG answer
        t0 = time.time()
        chunks     = retrieve_context(question)
        rag_answer = collect_stream(stream_answer(question))
        rag_time   = round(time.time() - t0, 2)
        f_rag      = score_faithfulness(rag_answer, chunks)
        total_rag += f_rag
 
        if verbose:
            print(f"\n[WITH RAG — {rag_time}s — faithfulness: {f_rag}]")
            print(rag_answer[:500] + ("…" if len(rag_answer) > 500 else ""))
            if chunks:
                print(f"  Top source: {chunks[0]['source']} (dist={chunks[0]['distance']})")
 
        # Bare LLM baseline
        t0        = time.time()
        base_answer = get_bare_answer(question)
        base_time   = round(time.time() - t0, 2)
        f_base      = score_faithfulness(base_answer, chunks)
        total_base += f_base
 
        if verbose:
            print(f"\n[WITHOUT RAG — {base_time}s — faithfulness: {f_base}]")
            print(base_answer[:500] + ("…" if len(base_answer) > 500 else ""))
 
        results.append({
            "question":             question,
            "rag_answer":           rag_answer,
            "baseline_answer":      base_answer,
            "faithfulness_rag":     f_rag,
            "faithfulness_baseline": f_base,
            "top_source":           chunks[0]["source"] if chunks else None,
            "rag_latency_s":        rag_time,
        })
 
    n           = len(questions)
    avg_rag     = round(total_rag / n, 3)
    avg_base    = round(total_base / n, 3)
    improvement = round(((avg_rag - avg_base) / max(avg_base, 0.001)) * 100, 1)
 
    summary = {
        "questions_evaluated":       n,
        "avg_faithfulness_rag":      avg_rag,
        "avg_faithfulness_baseline": avg_base,
        "improvement_pct":           improvement,
        "results":                   results,
    }
 
    print(f"\n{'='*60}")
    print("EVAL SUMMARY")
    print(f"  Questions:          {n}")
    print(f"  RAG faithfulness:   {avg_rag}")
    print(f"  Base faithfulness:  {avg_base}")
    print(f"  Improvement:        +{improvement}%")
    print(f"\n  PORTFOLIO STAT: RAG improved answer faithfulness by {improvement}%")
    print(f"{'='*60}")
 
    return summary

#--- Command-line interface----

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
 
    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline quality")
    parser.add_argument("--doc",       help="Path to document to ingest before eval")
    parser.add_argument("--questions", help="Path to JSON question file")
    parser.add_argument("--output",    default="eval_results.json")
    parser.add_argument("--quiet",     action="store_true")
    args = parser.parse_args()
 
    if args.doc:
        p = Path(args.doc)
        print(f"Ingesting {p.name} ...")
        r = ingest_document(p, source_name=p.name)
        print(f"  → {r['chunks']} chunks stored\n")
 
    questions = DEFAULT_QUESTIONS
    if args.questions:
        with open(args.questions) as f:
            questions = json.load(f)
 
    summary = run_eval(questions, verbose=not args.quiet)
 
    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
 
    print(f"\nFull results saved to {args.output}")
 
