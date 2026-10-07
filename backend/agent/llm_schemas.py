"""Pydantic models for LLM structured outputs (validated after JSON extraction)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubQuestionSchema(BaseModel):
    text: str
    modality: str = "any"
    needs_math: bool = False


class PlannerOutput(BaseModel):
    sub_questions: list[SubQuestionSchema] = Field(default_factory=list)


class CitationSchema(BaseModel):
    element_id: str | None = None
    quote: str | None = None


class ClaimSchema(BaseModel):
    text: str = ""
    citations: list[CitationSchema] = Field(default_factory=list)


class CalculationSchema(BaseModel):
    name: str = "calc"
    formula: str = "0"
    inputs: dict[str, float | int] = Field(default_factory=dict)


class AnswererOutput(BaseModel):
    answer: str = ""
    reasoning_summary: str | None = None
    claims: list[ClaimSchema] = Field(default_factory=list)
    calculations: list[CalculationSchema] = Field(default_factory=list)
    confidence: float = 0.5


class VerifierOutput(BaseModel):
    supported: bool = True
    reason: str = ""


class FigureSeriesSchema(BaseModel):
    name: str = ""
    values: list[float | int | str] = Field(default_factory=list)


class VlmAnswerExtraction(BaseModel):
    element_id: str = ""
    extracted_values: str = ""
    units: str = ""
    trend_summary: str = ""
    uncertain: bool = False


class FigureOutput(BaseModel):
    caption: str = ""
    chart_type: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    units: str = ""
    series: list[FigureSeriesSchema] = Field(default_factory=list)
    data_points: list[dict[str, float | int | str]] = Field(default_factory=list)
    key_trends: list[str] = Field(default_factory=list)
    values_markdown: str = ""
    uncertain: bool = False
    confidence: float = 0.5
