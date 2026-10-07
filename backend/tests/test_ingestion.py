from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from ingestion.pipeline import ingest_pdf  # noqa: E402


@pytest.fixture(scope="module")
def ensure_test_pack():
    subprocess.run([sys.executable, str(REPO / "scripts" / "make_test_pack.py")], check=True, cwd=REPO)


def test_ingest_quarterly_produces_elements(ensure_test_pack, tmp_path: Path):
    settings = Settings(
        GEMINI_API_KEY="",
        INDEX_DIR=tmp_path / "index",
    )
    pdf = REPO / "data" / "sample_docs" / "quarterly_report_2025.pdf"
    report = ingest_pdf(pdf, settings=settings)
    assert report.status in ("ok", "partial")
    assert report.elements_count > 5
    elements = json.loads((tmp_path / "index" / report.doc_id / "elements.json").read_text())
    types = {e["type"] for e in elements}
    assert "text" in types or "heading" in types


def test_damaged_pdf_does_not_crash(ensure_test_pack, tmp_path: Path):
    settings = Settings(INDEX_DIR=tmp_path / "index")
    pdf = REPO / "data" / "degraded" / "damaged.pdf"
    report = ingest_pdf(pdf, settings=settings)
    assert report.status in ("failed", "partial", "ok")
    # Must not raise; errors recorded
    assert isinstance(report.errors, list)


def test_ingest_all_summary(ensure_test_pack, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.index_dir = tmp_path / "index"

    from ingestion.pipeline import ingest_paths

    pdfs = list((REPO / "data" / "sample_docs").glob("*.pdf")) + list(
        (REPO / "data" / "degraded").glob("*.pdf")
    )
    reports = ingest_paths(pdfs, settings=settings)
    assert len(reports) >= 6
    names = {r.doc_name for r in reports}
    assert "quarterly_report_2025.pdf" in names
    assert "damaged.pdf" in names
