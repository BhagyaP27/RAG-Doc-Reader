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
