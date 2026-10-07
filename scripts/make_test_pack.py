#!/usr/bin/env python3
"""Generate synthetic PDF test pack and gold_questions.json (P1)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

from test_pack_data import (  # noqa: E402
    ABSTAIN_PHRASE,
    CHART_ONLY_PEAK_EFFICIENCY_Q3,
    PLANT_SUMMARY,
    Q2_TO_Q4_CAUSES,
    QUARTERLY_ROWS,
    RESEARCH_PAPER,
    efficiency_delta_q2_q4,
    get_quarter,
)

SAMPLE_DIR = _REPO / "data" / "sample_docs"
DEGRADED_DIR = _REPO / "data" / "degraded"
GOLD_PATH = _REPO / "data" / "gold_questions.json"


def _ensure_dirs() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    DEGRADED_DIR.mkdir(parents=True, exist_ok=True)


def _chart_bar_path() -> Path:
    out = _REPO / "data" / "cache" / "test_pack" / "bar_units.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    quarters = [r.quarter for r in QUARTERLY_ROWS]
    units = [r.units for r in QUARTERLY_ROWS]
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(quarters, units, color="#2563eb")
    ax.set_title("Quarterly Production Units")
    ax.set_ylabel("Units")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _chart_line_path() -> Path:
    """Line chart includes Q3 peak 91.7% — chart-only datum."""
    out = _REPO / "data" / "cache" / "test_pack" / "line_efficiency.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    quarters = [r.quarter for r in QUARTERLY_ROWS]
    eff = [r.efficiency_pct for r in QUARTERLY_ROWS]
    eff[2] = CHART_ONLY_PEAK_EFFICIENCY_Q3  # Q3 peak only on chart
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(quarters, eff, marker="o", color="#16a34a")
    ax.set_title("Efficiency Trend (with Q3 operational peak)")
    ax.set_ylabel("Efficiency %")
    for x, y in zip(quarters, eff):
        ax.annotate(f"{y}%", (x, y), textcoords="offset points", xytext=(0, 6), ha="center")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def build_quarterly_report_2025(path: Path) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["Normal"], alignment=TA_JUSTIFY, leading=14)
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    story: list = []

    story.append(Paragraph("Acme Manufacturing — Quarterly Production Report 2025", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "This report summarizes plant-wide production metrics for fiscal year 2025. "
            "Efficiency improvements from Q2 through Q4 reflect operational initiatives "
            "described in the narrative section below.",
            body,
        )
    )
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Production summary (table)", styles["Heading2"]))
    story.append(Spacer(1, 0.1 * inch))

    table_data = [
        ["Quarter", "Units", "Efficiency %", "Downtime (hrs)", "Defect rate %"],
    ]
    for r in QUARTERLY_ROWS:
        table_data.append(
            [r.quarter, f"{r.units:,}", str(r.efficiency_pct), str(r.downtime_hrs), str(r.defect_rate_pct)]
        )
    t = Table(table_data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    bar_path = _chart_bar_path()
    line_path = _chart_line_path()
    story.append(Paragraph("Charts", styles["Heading2"]))
    story.append(RLImage(str(bar_path), width=4.5 * inch, height=2.7 * inch))
    story.append(Spacer(1, 0.15 * inch))
    story.append(RLImage(str(line_path), width=4.5 * inch, height=2.7 * inch))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Drivers of Q2–Q4 efficiency change", styles["Heading2"]))
    cause_text = (
        "From Q2 to Q4, efficiency rose primarily because: (1) "
        + Q2_TO_Q4_CAUSES[0]
        + " (2) "
        + Q2_TO_Q4_CAUSES[1]
        + " (3) "
        + Q2_TO_Q4_CAUSES[2]
    )
    story.append(Paragraph(cause_text, body))
    doc.build(story)


def build_research_paper_two_column(path: Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    col_width = (letter[0] - 1.5 * inch) / 2 - 0.15 * inch

    two_col = ParagraphStyle(
        "TwoCol",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
    )

    fig_path = _REPO / "data" / "cache" / "test_pack" / "research_figure.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.bar(["BM25", "Dense", "Hybrid"], [0.62, 0.71, RESEARCH_PAPER["accuracy_pct"] / 100])
    ax.set_ylabel("F1 (normalized)")
    ax.set_title("Retrieval ablation")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)

    left_col = [
        Paragraph(RESEARCH_PAPER["title"], styles["Heading2"]),
        Paragraph(
            "We evaluate hybrid retrieval combining sparse and dense signals. "
            "Experiments use a fixed corpus of 12k pages with automatic layout parsing.",
            two_col,
        ),
        Paragraph(
            f"Mean latency was {RESEARCH_PAPER['latency_ms']} ms per query on CPU-only hardware.",
            two_col,
        ),
        Paragraph(
            f"Primary metric: {RESEARCH_PAPER['equation']}.",
            two_col,
        ),
    ]
    right_col = [
        Paragraph("Results", styles["Heading3"]),
        Paragraph(
            f"Hybrid retrieval achieved {RESEARCH_PAPER['accuracy_pct']}% answer accuracy "
            "on the development split.",
            two_col,
        ),
        RLImage(str(fig_path), width=col_width, height=col_width * 0.65),
        Paragraph(
            "Figure 1: Ablation over retriever components. Hybrid fusion improves recall@8.",
            ParagraphStyle("Cap", parent=two_col, fontSize=8, textColor=colors.grey),
        ),
        Spacer(1, 0.1 * inch),
        Paragraph("Table 1 — Benchmark rows", styles["Heading3"]),
    ]

    table_data = [["System", "F1", "Latency (ms)"], ["Hybrid", "0.78", str(RESEARCH_PAPER["latency_ms"])]]
    tbl = Table(table_data)
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    right_col.append(tbl)

    # Two-column layout via nested table
    layout = Table([[left_col, right_col]], colWidths=[col_width, col_width])
    layout.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build([layout])


def build_annual_summary_2025(path: Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    story = [
        Paragraph("Enterprise Annual Summary 2025", styles["Title"]),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "Consolidated totals across manufacturing sites for cross-site comparison.",
            styles["Normal"],
        ),
        Spacer(1, 0.2 * inch),
    ]
    rows = [["Plant", "Site", "Total units 2025", "Avg efficiency %"]]
    for plant, info in PLANT_SUMMARY.items():
        rows.append(
            [
                plant,
                info["site"],
                f"{info['total_units_2025']:,}",
                str(info["avg_efficiency_pct"]),
            ]
        )
    t = Table(rows)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story.append(t)
    doc.build(story)


def build_scanned_quarterly(source: Path, dest: Path) -> None:
    import fitz  # PyMuPDF

    src = fitz.open(source)
    pix = src[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img = img.rotate(2.5, expand=True, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    arr = np.array(img).astype(np.int16)
    noise = np.random.default_rng(42).integers(-18, 18, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=45)
    buf.seek(0)

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=buf.read())
    doc.save(dest)
    doc.close()
    src.close()


def build_lowquality_photo_page(path: Path) -> None:
    import fitz

    img = Image.new("RGB", (800, 1000), (240, 235, 230))
    arr = np.array(img)
    arr = (arr * np.random.default_rng(7).uniform(0.7, 1.0, arr.shape)).astype(np.uint8)
    img = Image.fromarray(arr).resize((400, 500), Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=15)
    buf.seek(0)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(50, 100, 562, 692), stream=buf.read())
    doc.save(path)
    doc.close()


def build_damaged_pdf(source: Path, dest: Path) -> None:
    data = source.read_bytes()
    dest.write_bytes(data[: max(len(data) // 3, 1024)])


def build_gold_questions() -> list[dict]:
    q2 = get_quarter("Q2")
    q4 = get_quarter("Q4")
    delta = efficiency_delta_q2_q4()
    questions: list[dict] = []

    def add(
        qid: str,
        question: str,
        qtype: str,
        expected_answer: str,
        *,
        expected_numeric: float | None = None,
        expected_docs: list[str] | None = None,
        expected_pages: list[int] | None = None,
        notes: str = "",
    ) -> None:
        questions.append(
            {
                "id": qid,
                "question": question,
                "type": qtype,
                "expected_answer": expected_answer,
                "expected_numeric": expected_numeric,
                "expected_docs": expected_docs or [],
                "expected_pages": expected_pages or [1],
                "notes": notes,
            }
        )

    add(
        "q001",
        "What was Q4 production efficiency percentage?",
        "table",
        str(q4.efficiency_pct),
        expected_numeric=q4.efficiency_pct,
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q002",
        "What was Q2 production efficiency percentage?",
        "table",
        str(q2.efficiency_pct),
        expected_numeric=q2.efficiency_pct,
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q003",
        "By how many percentage points did efficiency change from Q2 to Q4?",
        "math",
        str(delta),
        expected_numeric=delta,
        expected_docs=["quarterly_report_2025.pdf"],
        notes="Requires math tool; do not let LLM compute.",
    )
    add(
        "q004",
        "List the three biggest reasons given for the Q2 to Q4 efficiency improvement.",
        "text",
        "; ".join(Q2_TO_Q4_CAUSES),
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q005",
        "What peak efficiency percentage appears on the line chart for Q3?",
        "chart",
        str(CHART_ONLY_PEAK_EFFICIENCY_Q3),
        expected_numeric=CHART_ONLY_PEAK_EFFICIENCY_Q3,
        expected_docs=["quarterly_report_2025.pdf"],
        notes="Value only on chart, not in table.",
    )
    add(
        "q006",
        "Compare production efficiency between Q2 and Q4 and identify the three biggest reasons for the change.",
        "cross_doc",
        f"Q2 {q2.efficiency_pct}% vs Q4 {q4.efficiency_pct}%; causes: " + "; ".join(Q2_TO_Q4_CAUSES),
        expected_docs=["quarterly_report_2025.pdf"],
        notes="Demo question — text + table + chart.",
    )
    add(
        "q007",
        "How many units were produced in Q3?",
        "table",
        str(get_quarter("Q3").units),
        expected_numeric=float(get_quarter("Q3").units),
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q008",
        "What was Q1 downtime in hours?",
        "table",
        str(get_quarter("Q1").downtime_hrs),
        expected_numeric=get_quarter("Q1").downtime_hrs,
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q009",
        "Which quarter had the highest defect rate?",
        "table",
        "Q1",
        expected_docs=["quarterly_report_2025.pdf"],
    )
    add(
        "q010",
        "What is Plant B total units in 2025?",
        "table",
        str(PLANT_SUMMARY["Plant B"]["total_units_2025"]),
        expected_numeric=float(PLANT_SUMMARY["Plant B"]["total_units_2025"]),
        expected_docs=["annual_summary_2025.pdf"],
    )
    add(
        "q011",
        "Which plant has higher average efficiency, Plant A or Plant B?",
        "cross_doc",
        "Plant B",
        expected_docs=["annual_summary_2025.pdf"],
    )
    add(
        "q012",
        "What is Plant A site location?",
        "text",
        PLANT_SUMMARY["Plant A"]["site"],
        expected_docs=["annual_summary_2025.pdf"],
    )
    add(
        "q013",
        "What hybrid retrieval accuracy percent is reported in the research paper?",
        "table",
        str(RESEARCH_PAPER["accuracy_pct"]),
        expected_numeric=RESEARCH_PAPER["accuracy_pct"],
        expected_docs=["research_paper_two_column.pdf"],
    )
    add(
        "q014",
        "What mean query latency in ms is reported?",
        "text",
        str(RESEARCH_PAPER["latency_ms"]),
        expected_numeric=float(RESEARCH_PAPER["latency_ms"]),
        expected_docs=["research_paper_two_column.pdf"],
    )
    add(
        "q015",
        "What F1 equation is stated in the paper?",
        "text",
        RESEARCH_PAPER["equation"],
        expected_docs=["research_paper_two_column.pdf"],
    )

    # Unanswerable / abstain
    for i, topic in enumerate(
        [
            "2024 revenue",
            "CEO home address",
            "Mars colony production",
            "employee social security numbers",
            "stock ticker symbol",
        ],
        start=1,
    ):
        add(
            f"u{i:03d}",
            f"What is the {topic} mentioned in the documents?",
            "unanswerable",
            ABSTAIN_PHRASE,
            expected_docs=[],
            notes="Must abstain.",
        )

    # Fill to 50+ with typed variants
    extras = [
        ("q016", "Q4 defect rate percent?", "table", str(q4.defect_rate_pct), ["quarterly_report_2025.pdf"]),
        ("q017", "Q2 units produced?", "table", str(q2.units), ["quarterly_report_2025.pdf"]),
        ("q018", "Sum of Q1 and Q2 units?", "math", str(get_quarter("Q1").units + q2.units), ["quarterly_report_2025.pdf"]),
        ("q019", "Plant B average efficiency?", "table", str(PLANT_SUMMARY["Plant B"]["avg_efficiency_pct"]), ["annual_summary_2025.pdf"]),
        ("q020", "Plant A total units?", "table", str(PLANT_SUMMARY["Plant A"]["total_units_2025"]), ["annual_summary_2025.pdf"]),
        ("q021", "Does Q4 have lower downtime than Q2?", "text", "yes", ["quarterly_report_2025.pdf"]),
        ("q022", "Title of research paper?", "text", RESEARCH_PAPER["title"], ["research_paper_two_column.pdf"]),
        ("q023", "Which Q has 46000 units?", "table", "Q3", ["quarterly_report_2025.pdf"]),
        ("q024", "Q3 efficiency in table?", "table", str(get_quarter("Q3").efficiency_pct), ["quarterly_report_2025.pdf"]),
        ("q025", "Combined Plant A and B units?", "math", str(PLANT_SUMMARY["Plant A"]["total_units_2025"] + PLANT_SUMMARY["Plant B"]["total_units_2025"]), ["annual_summary_2025.pdf"]),
        ("q026", "First Q2–Q4 cause text?", "text", Q2_TO_Q4_CAUSES[0], ["quarterly_report_2025.pdf"]),
        ("q027", "Second Q2–Q4 cause?", "text", Q2_TO_Q4_CAUSES[1], ["quarterly_report_2025.pdf"]),
        ("q028", "Third Q2–Q4 cause?", "text", Q2_TO_Q4_CAUSES[2], ["quarterly_report_2025.pdf"]),
        ("q029", "Q1 efficiency?", "table", str(get_quarter("Q1").efficiency_pct), ["quarterly_report_2025.pdf"]),
        ("q030", "Q4 downtime hours?", "table", str(q4.downtime_hrs), ["quarterly_report_2025.pdf"]),
        ("s001", "Q4 efficiency from scanned report?", "scanned", str(q4.efficiency_pct), ["scanned_quarterly_report.pdf"]),
        ("s002", "Is scanned report readable at all?", "scanned", "partial", ["scanned_quarterly_report.pdf"], "Degraded scan"),
        ("img001", "Does low quality photo page contain extractable text?", "image", ABSTAIN_PHRASE, ["lowquality_photo_page.pdf"], "Mostly blank noise"),
        ("cd001", "Which plant produced more total units?", "cross_doc", "Plant B", ["annual_summary_2025.pdf"]),
        ("cd002", "Compare Plant A and Plant B average efficiency values.", "cross_doc", f"Plant A {PLANT_SUMMARY['Plant A']['avg_efficiency_pct']}% vs Plant B {PLANT_SUMMARY['Plant B']['avg_efficiency_pct']}%", ["annual_summary_2025.pdf"]),
    ]
    for row in extras:
        qid, qu, qt, ans, docs = row[0], row[1], row[2], row[3], row[4]
        notes = row[5] if len(row) > 5 else ""
        add(qid, qu, qt, ans, expected_docs=docs, notes=notes)

    # Pad numeric/text until 50
    n = len(questions)
    idx = 31
    while n < 50:
        r = QUARTERLY_ROWS[(idx - 31) % len(QUARTERLY_ROWS)]
        add(
            f"q{idx:03d}",
            f"Repeat check: {r.quarter} defect rate?",
            "table",
            str(r.defect_rate_pct),
            expected_numeric=r.defect_rate_pct,
            expected_docs=["quarterly_report_2025.pdf"],
        )
        idx += 1
        n = len(questions)

    return questions


def main() -> None:
    _ensure_dirs()
    quarterly = SAMPLE_DIR / "quarterly_report_2025.pdf"
    research = SAMPLE_DIR / "research_paper_two_column.pdf"
    annual = SAMPLE_DIR / "annual_summary_2025.pdf"
    scanned = DEGRADED_DIR / "scanned_quarterly_report.pdf"
    lowq = DEGRADED_DIR / "lowquality_photo_page.pdf"
    damaged = DEGRADED_DIR / "damaged.pdf"

    print("Building quarterly_report_2025.pdf ...")
    build_quarterly_report_2025(quarterly)
    print("Building research_paper_two_column.pdf ...")
    build_research_paper_two_column(research)
    print("Building annual_summary_2025.pdf ...")
    build_annual_summary_2025(annual)
    print("Building scanned_quarterly_report.pdf ...")
    build_scanned_quarterly(quarterly, scanned)
    print("Building lowquality_photo_page.pdf ...")
    build_lowquality_photo_page(lowq)
    print("Building damaged.pdf ...")
    build_damaged_pdf(quarterly, damaged)

    gold = build_gold_questions()
    GOLD_PATH.write_text(json.dumps(gold, indent=2), encoding="utf-8")
    print(f"Wrote {len(gold)} gold questions -> {GOLD_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
