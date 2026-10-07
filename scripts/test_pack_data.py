"""
Canonical synthetic dataset for PDF generation and gold answers.
All expected answers in gold_questions.json must derive from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ABSTAIN_PHRASE = "not found in the provided documents"

# Chart-only value: peak efficiency in Q3 (line chart), NOT duplicated in table narrative.
CHART_ONLY_PEAK_EFFICIENCY_Q3 = 91.7


@dataclass(frozen=True)
class QuarterRow:
    quarter: str
    units: int
    efficiency_pct: float
    downtime_hrs: float
    defect_rate_pct: float


QUARTERLY_ROWS: tuple[QuarterRow, ...] = (
    QuarterRow("Q1", 42000, 82.4, 120.0, 2.1),
    QuarterRow("Q2", 44500, 84.0, 105.0, 1.9),
    QuarterRow("Q3", 46000, 88.5, 98.0, 1.7),
    QuarterRow("Q4", 47200, 89.2, 88.0, 1.5),
)

Q2_TO_Q4_CAUSES: tuple[str, ...] = (
    "Predictive maintenance rollout reduced unplanned downtime.",
    "Operator cross-training improved line changeover speed.",
    "Supplier quality program lowered incoming defect rates.",
)

PLANT_SUMMARY: dict[str, dict[str, Any]] = {
    "Plant A": {
        "total_units_2025": 82000,
        "avg_efficiency_pct": 86.1,
        "site": "Midwest",
    },
    "Plant B": {
        "total_units_2025": 97700,
        "avg_efficiency_pct": 87.4,
        "site": "Southwest",
    },
}

RESEARCH_PAPER = {
    "title": "Hybrid Retrieval for Document QA",
    "accuracy_pct": 78.3,
    "latency_ms": 412,
    "equation": "F1 = 2 * (precision * recall) / (precision + recall)",
}


def quarterly_table_markdown() -> str:
    lines = [
        "| Quarter | Units | Efficiency % | Downtime (hrs) | Defect rate % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in QUARTERLY_ROWS:
        lines.append(
            f"| {r.quarter} | {r.units:,} | {r.efficiency_pct} | {r.downtime_hrs} | {r.defect_rate_pct} |"
        )
    return "\n".join(lines)


def get_quarter(quarter: str) -> QuarterRow:
    for r in QUARTERLY_ROWS:
        if r.quarter == quarter:
            return r
    raise KeyError(quarter)


def efficiency_delta_q2_q4() -> float:
    return round(get_quarter("Q4").efficiency_pct - get_quarter("Q2").efficiency_pct, 2)
