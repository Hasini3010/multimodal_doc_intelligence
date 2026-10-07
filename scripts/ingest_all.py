#!/usr/bin/env python3
"""Ingest all sample and degraded PDFs into data/index/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from ingestion.pipeline import ingest_paths  # noqa: E402

SAMPLE = REPO / "data" / "sample_docs"
DEGRADED = REPO / "data" / "degraded"


def main() -> None:
    pdfs = sorted(SAMPLE.glob("*.pdf")) + sorted(DEGRADED.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found. Run: python scripts/make_test_pack.py")
        sys.exit(1)

    settings = get_settings()
    reports = ingest_paths(pdfs, settings=settings)
    out = REPO / "data" / "index" / "ingestion_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([r.model_dump() for r in reports], indent=2),
        encoding="utf-8",
    )

    print(f"Ingested {len(reports)} documents:")
    for r in reports:
        print(f"  - {r.doc_name}: {r.status} ({r.elements_count} elements, skipped pages {r.pages_skipped})")
        for err in r.errors:
            print(f"      err: {err}")

    try:
        from indexing.store import build_document_index

        idx = build_document_index(settings.resolve_path(settings.index_dir), rebuild_vectors=True)
        print(f"Built search index over {len(idx.elements)} elements.")
    except Exception as exc:
        print(f"Index build skipped/failed: {exc}")


if __name__ == "__main__":
    main()
