#!/usr/bin/env python3
"""Build BM25 + vector index from data/index/*/elements.json."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from indexing.store import build_document_index  # noqa: E402


def main() -> None:
    settings = get_settings()
    index_dir = settings.resolve_path(settings.index_dir)
    doc_index = build_document_index(index_dir, rebuild_vectors=True)
    print(f"Indexed {len(doc_index.elements)} elements -> {index_dir}")


if __name__ == "__main__":
    main()
