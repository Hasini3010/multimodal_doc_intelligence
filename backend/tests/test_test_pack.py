"""P1 gate: PDFs open and gold answers match canonical source data."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

_REPO = Path(__file__).resolve().parents[2]
SCRIPTS = _REPO / "scripts"
GOLD_PATH = _REPO / "data" / "gold_questions.json"
SAMPLE_DIR = _REPO / "data" / "sample_docs"
DEGRADED_DIR = _REPO / "data" / "degraded"


@pytest.fixture(scope="module", autouse=True)
def generate_test_pack():
    subprocess.run(
        [sys.executable, str(SCRIPTS / "make_test_pack.py")],
        cwd=_REPO,
        check=True,
    )


def test_pdfs_exist_and_open():
    paths = [
        SAMPLE_DIR / "quarterly_report_2025.pdf",
        SAMPLE_DIR / "research_paper_two_column.pdf",
        SAMPLE_DIR / "annual_summary_2025.pdf",
        DEGRADED_DIR / "scanned_quarterly_report.pdf",
        DEGRADED_DIR / "lowquality_photo_page.pdf",
        DEGRADED_DIR / "damaged.pdf",
    ]
    for path in paths:
        assert path.exists(), path
        if path.name == "damaged.pdf":
            try:
                doc = fitz.open(path)
                _ = len(doc)
                doc.close()
            except Exception:
                pass  # truncated file may not open fully
            continue
        doc = fitz.open(path)
        assert len(doc) >= 1, path.name
        doc.close()


def test_gold_question_count():
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert len(gold) >= 50


def test_gold_matches_source_data():
    sys.path.insert(0, str(SCRIPTS))
    from test_pack_data import (  # noqa: WPS433
        ABSTAIN_PHRASE,
        CHART_ONLY_PEAK_EFFICIENCY_Q3,
        PLANT_SUMMARY,
        Q2_TO_Q4_CAUSES,
        efficiency_delta_q2_q4,
        get_quarter,
    )

    gold = {q["id"]: q for q in json.loads(GOLD_PATH.read_text(encoding="utf-8"))}

    q4 = get_quarter("Q4")
    assert gold["q001"]["expected_answer"] == str(q4.efficiency_pct)
    assert gold["q003"]["expected_numeric"] == efficiency_delta_q2_q4()
    assert gold["q005"]["expected_numeric"] == CHART_ONLY_PEAK_EFFICIENCY_Q3
    assert all(c in gold["q004"]["expected_answer"] for c in Q2_TO_Q4_CAUSES)
    assert gold["u001"]["expected_answer"] == ABSTAIN_PHRASE
    assert gold["q010"]["expected_answer"] == str(PLANT_SUMMARY["Plant B"]["total_units_2025"])
