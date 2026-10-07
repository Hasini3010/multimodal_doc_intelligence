"""Heuristic table extraction from text blocks."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd


def looks_like_table(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    pipe_rows = sum(1 for ln in lines if ln.count("|") >= 2)
    if pipe_rows >= 2:
        return True
    tab_rows = sum(1 for ln in lines if "\t" in ln)
    if tab_rows >= 2:
        return True
    # Multiple columns separated by 2+ spaces
    multi_col = sum(1 for ln in lines if len(re.split(r"\s{2,}", ln)) >= 3)
    return multi_col >= 2


def text_to_table_artifacts(text: str, out_dir: Path, stem: str) -> tuple[str, str | None]:
    """Return markdown and optional csv path."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows: list[list[str]] = []
    for ln in lines:
        if "|" in ln:
            cells = [c.strip() for c in ln.split("|") if c.strip()]
        else:
            cells = re.split(r"\s{2,}|\t", ln)
            cells = [c.strip() for c in cells if c.strip()]
        if cells:
            rows.append(cells)

    if not rows:
        return text, None

    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(norm[1:], columns=norm[0] if norm else None)

    md_lines = ["| " + " | ".join(norm[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for r in norm[1:]:
        md_lines.append("| " + " | ".join(r) + " |")
    markdown = "\n".join(md_lines)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stem}.csv"
    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
    return markdown, str(csv_path)
