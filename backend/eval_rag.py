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