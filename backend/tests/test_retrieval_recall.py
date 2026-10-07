"""P3 gate: recall@8 on gold expected pages (hybrid + rerank)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def built_index(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("idx")
    subprocess.run([sys.executable, str(REPO / "scripts" / "make_test_pack.py")], check=True, cwd=REPO)

    from app.config import Settings
    from ingestion.pipeline import ingest_paths

    settings = Settings(INDEX_DIR=tmp / "index")
    pdfs = sorted((REPO / "data" / "sample_docs").glob("*.pdf"))
    ingest_paths(pdfs, settings=settings)

    from indexing.store import build_document_index

    index_dir = settings.resolve_path(settings.index_dir)
    doc_index = build_document_index(index_dir, rebuild_vectors=True)
    return doc_index, index_dir


def test_recall_at_8_on_gold(built_index):
    doc_index, _ = built_index
    gold = json.loads((REPO / "data" / "gold_questions.json").read_text(encoding="utf-8"))
    # Answerable questions with expected docs in sample set
    subset = [
        q
        for q in gold
        if q["type"] != "unanswerable"
        and q.get("expected_docs")
        and all(
            (REPO / "data" / "sample_docs" / d).exists() for d in q["expected_docs"]
        )
    ][:15]

    from retrieval.hybrid import hybrid_search
    from retrieval.rerank import rerank_hits

    hits = 0
    total = 0
    for q in subset:
        total += 1
        expected_pages = set(q.get("expected_pages") or [])
        expected_docs = set(q.get("expected_docs") or [])
        raw_hits = hybrid_search(doc_index, q["question"], top_k=20, doc_ids=list(expected_docs))
        top = rerank_hits(q["question"], raw_hits, top_k=8)
        ok = any(
            h.element.doc_name in expected_docs and h.element.page in expected_pages
            for h in top
        )
        if ok:
            hits += 1

    recall = hits / total if total else 0.0
    print(f"\nrecall@8 (subset n={total}): {recall:.3f} ({hits}/{total})")
    assert total > 0
    assert recall >= 0.35, f"recall@8 too low: {recall:.3f}"
