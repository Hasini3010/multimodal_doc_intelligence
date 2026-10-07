"""Ingestion element and report schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import BBox

ElementType = Literal["text", "table", "figure", "caption", "heading"]
SourceMethod = Literal["text-layer", "ocr", "vlm", "heuristic"]


class DocumentElement(BaseModel):
    element_id: str
    doc_id: str
    doc_name: str
    page: int = Field(ge=1)
    bbox: BBox
    section: str | None = None
    type: ElementType
    source_method: SourceMethod
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    text: str | None = None
    table_markdown: str | None = None
    table_csv_path: str | None = None
    crop_path: str | None = None


class PageReport(BaseModel):
    page: int
    status: Literal["ok", "skipped", "error"] = "ok"
    message: str | None = None
    ocr_used: bool = False


class IngestionReport(BaseModel):
    doc_id: str
    doc_name: str
    sha256: str
    status: Literal["ok", "partial", "failed"] = "ok"
    pages_total: int = 0
    pages_processed: int = 0
    pages_skipped: list[int] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    layout_backend: str = "pymupdf"
    elements_count: int = 0
