"""Render PDF pages to PNG at target DPI."""

from __future__ import annotations

from pathlib import Path

import pymupdf


def render_page(pdf_path: Path, page_index: int, out_path: Path, dpi: int = 200) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        page = doc[page_index]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        pix.save(str(out_path))
    finally:
        doc.close()
    return out_path
