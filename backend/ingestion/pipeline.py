"""End-to-end PDF ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pymupdf

from app.config import Settings, get_settings
from ingestion.figures import extract_figure_json, figure_index_text
from ingestion.layout import extract_page_elements
from ingestion.models import IngestionReport, PageReport
from ingestion.repair import repair_pdf
from ingestion.render import render_page

logger = logging.getLogger(__name__)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_pdf(pdf_path: Path, settings: Settings | None = None) -> IngestionReport:
    settings = settings or get_settings()
    pdf_path = Path(pdf_path)
    doc_name = pdf_path.name
    sha = file_sha256(pdf_path)
    doc_id = sha[:16]

    index_root = settings.resolve_path(settings.index_dir) / doc_id
    if (index_root / "elements.json").exists() and (index_root / "meta.json").exists():
        meta = json.loads((index_root / "meta.json").read_text(encoding="utf-8"))
        if meta.get("sha256") == sha:
            logger.info("Cache hit for %s (%s)", doc_name, doc_id)
            cached = IngestionReport.model_validate(meta["report"])
            return cached.model_copy(update={"ingestion_cache_hit": True})

    index_root.mkdir(parents=True, exist_ok=True)
    pages_dir = index_root / "pages"
    crops_dir = index_root / "crops"
    tables_dir = index_root / "tables"
    pages_dir.mkdir(exist_ok=True)
    crops_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    repair_cache = settings.resolve_path(settings.index_dir) / "_repair_cache"
    repaired_path, _, repair_err = repair_pdf(pdf_path, cache_dir=repair_cache)
    cleanup_repaired = repaired_path != pdf_path
    report = IngestionReport(
        doc_id=doc_id,
        doc_name=doc_name,
        sha256=sha,
        layout_backend="pymupdf",
    )

    if repair_err and pdf_path.name == "damaged.pdf":
        report.errors.append(f"repair: {repair_err}")

    open_path = repaired_path
    doc: pymupdf.Document | None = None
    try:
        doc = pymupdf.open(open_path)
    except Exception as exc:
        report.status = "failed"
        report.errors.append(f"open: {exc}")
        _write_meta(index_root, sha, doc_name, doc_id, report, [])
        if cleanup_repaired and repaired_path.exists():
            repaired_path.unlink(missing_ok=True)
        return report

    assert doc is not None
    report.pages_total = len(doc)
    all_elements: list[dict] = []
    page_reports: list[PageReport] = []

    for page_index in range(len(doc)):
        page_num = page_index + 1
        try:
            page_png = pages_dir / f"page_{page_num:03d}.png"
            render_page(open_path, page_index, page_png, dpi=200)
            elements, ocr_used = extract_page_elements(
                doc,
                page_index,
                doc_id=doc_id,
                doc_name=doc_name,
                page_image_path=page_png,
                crops_dir=crops_dir,
                tables_dir=tables_dir,
            )
            all_elements.extend(e.model_dump() for e in elements)
            report.pages_processed += 1
            page_reports.append(PageReport(page=page_num, ocr_used=ocr_used))
        except Exception as exc:
            logger.exception("Page %s failed for %s", page_num, doc_name)
            report.pages_skipped.append(page_num)
            report.errors.append(f"page {page_num}: {exc}")
            page_reports.append(PageReport(page=page_num, status="error", message=str(exc)))

    doc.close()
    if cleanup_repaired and repaired_path.exists():
        repaired_path.unlink(missing_ok=True)

    _enrich_figures(all_elements, settings)
    report.elements_count = len(all_elements)
    if report.pages_skipped:
        report.status = "partial" if report.pages_processed else "failed"
    elif report.errors:
        report.status = "partial"

    (index_root / "elements.json").write_text(
        json.dumps(all_elements, indent=2), encoding="utf-8"
    )
    (index_root / "page_reports.json").write_text(
        json.dumps([p.model_dump() for p in page_reports], indent=2),
        encoding="utf-8",
    )
    _write_meta(index_root, sha, doc_name, doc_id, report, all_elements)

    # Keep a copy of source pdf reference
    ref = index_root / "source_ref.json"
    ref.write_text(
        json.dumps({"path": str(pdf_path.resolve()), "sha256": sha}, indent=2),
        encoding="utf-8",
    )
    return report


def _enrich_figures(elements: list[dict], settings: Settings) -> None:
    for el in elements:
        if el.get("type") != "figure":
            continue
        crop = el.get("crop_path")
        if not crop:
            continue
        path = Path(crop)
        if not path.is_absolute():
            path = settings.resolve_path(settings.index_dir) / el["doc_id"] / path.name
            if not path.exists():
                path = Path(crop)
        vlm = extract_figure_json(path, settings=settings)
        if vlm:
            el["figure_json"] = vlm
            el["vlm_index_text"] = figure_index_text(vlm)


def _write_meta(
    index_root: Path,
    sha: str,
    doc_name: str,
    doc_id: str,
    report: IngestionReport,
    elements: list[dict],
) -> None:
    meta = {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "sha256": sha,
        "report": report.model_dump(),
        "element_count": len(elements),
    }
    (index_root / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def ingest_paths(paths: list[Path], settings: Settings | None = None) -> list[IngestionReport]:
    reports: list[IngestionReport] = []
    for p in paths:
        try:
            reports.append(ingest_pdf(p, settings=settings))
        except Exception as exc:
            logger.exception("Ingest crashed on %s", p)
            reports.append(
                IngestionReport(
                    doc_id="unknown",
                    doc_name=p.name,
                    sha256="",
                    status="failed",
                    errors=[str(exc)],
                )
            )
    return reports
