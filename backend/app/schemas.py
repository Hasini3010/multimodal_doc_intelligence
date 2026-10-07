"""Shared Pydantic schemas for API and agent I/O."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Normalized bounding box (0–1) relative to page width/height."""

    x0: float = Field(ge=0.0, le=1.0)
    y0: float = Field(ge=0.0, le=1.0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    doc_id: str
    doc_name: str | None = None
    page: int = Field(ge=1)
    section: str | None = None
    element_id: str | None = None
    bbox: BBox | None = None
    quote: str | None = None


class CalculationResult(BaseModel):
    name: str
    formula: str
    inputs: dict[str, Any]
    result: float | int | str


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None


class AskResponse(BaseModel):
    answer: str
    reasoning_summary: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    calculations: list[CalculationResult] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    abstained: bool = False


class DocumentSummary(BaseModel):
    doc_id: str
    doc_name: str
    page_count: int
    sha256: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    gemini_configured: bool = False
    models: dict[str, str] = Field(default_factory=dict)
