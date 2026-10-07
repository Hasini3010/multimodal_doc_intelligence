"""Layout extraction using PyMuPDF text blocks and image regions."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf

from app.schemas import BBox
from ingestion.models import DocumentElement
from ingestion.ocr import run_ocr
from ingestion.tables import looks_like_table, text_to_table_artifacts


def _clamp_bbox(x0: float, y0: float, x1: float, y1: float) -> BBox:
    return BBox(
        x0=max(0.0, min(1.0, x0)),
        y0=max(0.0, min(1.0, y0)),
        x1=max(0.0, min(1.0, x1)),
        y1=max(0.0, min(1.0, y1)),
    )


def _norm_bbox(rect: pymupdf.Rect, page: pymupdf.Page) -> BBox:
    w, h = page.rect.width, page.rect.height
    return _clamp_bbox(rect.x0 / w, rect.y0 / h, rect.x1 / w, rect.y1 / h)


def _element_id(doc_id: str, page: int, kind: str, seed: str) -> str:
    h = hashlib.sha256(f"{doc_id}:{page}:{kind}:{seed}".encode()).hexdigest()[:12]
    return f"{doc_id[:8]}_{page}_{kind}_{h}"


def extract_page_elements(
    doc: pymupdf.Document,
    page_index: int,
    *,
    doc_id: str,
    doc_name: str,
    page_image_path: Path | None,
    crops_dir: Path,
    tables_dir: Path,
    min_text_chars: int = 40,
) -> tuple[list[DocumentElement], bool]:
    """Returns elements and whether OCR was used."""
    page = doc[page_index]
    page_num = page_index + 1
    elements: list[DocumentElement] = []
    current_section: str | None = None
    ocr_used = False

    text_plain = page.get_text("text") or ""
    use_ocr = len(text_plain.strip()) < min_text_chars

    if use_ocr and page_image_path and page_image_path.exists():
        ocr_used = True
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
        blocks = run_ocr(page_image_path, page_width=pix.width, page_height=pix.height)
        for i, ob in enumerate(blocks):
            bbox = _clamp_bbox(*ob.bbox_norm)
            el_type = "heading" if ob.text.isupper() and len(ob.text) < 80 else "text"
            if el_type == "heading":
                current_section = ob.text
            elements.append(
                DocumentElement(
                    element_id=_element_id(doc_id, page_num, "ocr", str(i)),
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page=page_num,
                    bbox=bbox,
                    section=current_section,
                    type=el_type,
                    source_method="ocr",
                    confidence=ob.confidence,
                    text=ob.text,
                )
            )
        if elements:
            return elements, ocr_used

    blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT).get("blocks", [])
    block_idx = 0
    for block in blocks:
        if block.get("type") != 0:
            continue
        lines_text: list[str] = []
        rect: pymupdf.Rect | None = None
        max_size = 0.0
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = span.get("text", "")
                lines_text.append(t)
                max_size = max(max_size, float(span.get("size", 0)))
                sb = pymupdf.Rect(span["bbox"])
                rect = sb if rect is None else rect | sb
        text = "".join(lines_text).strip()
        if not text or rect is None:
            continue

        bbox = _norm_bbox(rect, page)
        if max_size >= 14 and len(text) < 120:
            el_type = "heading"
            current_section = text
        elif looks_like_table(text):
            el_type = "table"
        else:
            el_type = "text"

        md, csv_path = (None, None)
        if el_type == "table":
            md, csv_path = text_to_table_artifacts(
                text, tables_dir, f"p{page_num}_b{block_idx}"
            )

        elements.append(
            DocumentElement(
                element_id=_element_id(doc_id, page_num, el_type, text[:64]),
                doc_id=doc_id,
                doc_name=doc_name,
                page=page_num,
                bbox=bbox,
                section=current_section,
                type=el_type,
                source_method="text-layer",
                confidence=0.95,
                text=text,
                table_markdown=md,
                table_csv_path=csv_path,
            )
        )
        block_idx += 1

    # Large images -> figure placeholders (VLM in P3)
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for r_i, rect in enumerate(rects or [pymupdf.Rect(0, 0, page.rect.width, page.rect.height * 0.3)]):
            if rect.width * rect.height < (page.rect.width * page.rect.height) * 0.02:
                continue
            bbox = _norm_bbox(rect, page)
            crop_name = f"p{page_num}_fig_{img_index}_{r_i}.png"
            crop_path = crops_dir / crop_name
            try:
                pix = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(2, 2))
                crop_path.parent.mkdir(parents=True, exist_ok=True)
                pix.save(str(crop_path))
            except Exception:
                crop_path = None
            elements.append(
                DocumentElement(
                    element_id=_element_id(doc_id, page_num, "figure", crop_name),
                    doc_id=doc_id,
                    doc_name=doc_name,
                    page=page_num,
                    bbox=bbox,
                    section=current_section,
                    type="figure",
                    source_method="heuristic",
                    confidence=0.7,
                    text=None,
                    crop_path=str(crop_path) if crop_path else None,
                )
            )

    return elements, ocr_used
