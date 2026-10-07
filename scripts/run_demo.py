#!/usr/bin/env python3
"""Run demo questions through the /ask pipeline and print structured output."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(REPO / ".env")
os.environ.setdefault("VERIFIER_SKIP_LLM", "1")

DEMO_QUESTIONS = [
    "Compare production efficiency between Q2 and Q4, identify the three biggest reasons for the change, and show me the proof",
    "What peak efficiency percentage appears on the line chart for Q3?",
    "Which plant has higher average efficiency, Plant A or Plant B?",
    "What is the CEO home address mentioned in the documents?",
]


def main() -> None:
    from app.config import get_settings
    from agent.query_pipeline import ask

    settings = get_settings()
    if not settings.gemini_api_key.strip():
        print("GEMINI_API_KEY is not set in .env — demo requires Gemini for /ask.")
        sys.exit(1)

    index_dir = settings.resolve_path(settings.index_dir)
    if not index_dir.exists():
        print("Run: python scripts/ingest_all.py first")
        sys.exit(1)

    print("=== Multimodal Document Intelligence Demo ===\n")
    for i, question in enumerate(DEMO_QUESTIONS, 1):
        print(f"--- Q{i}: {question}\n")
        resp = ask(question)
        print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False))
        print()

    print("Open http://localhost:3000 with backend on :8000 for the UI demo.")


if __name__ == "__main__":
    main()
