"""Pydantic schemas used across API responses."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Basic heartbeat flag.")


class QuestionAnswerItem(BaseModel):
    question: str = Field(..., description="Question text as written on the form.")
    answer: str = Field(..., description="Parsed answer or selection.")


class ParserDebugBlock(BaseModel):
    line: str = Field(..., description="Raw textual line provided to structuring step.")
    confidence: float = Field(..., description="Confidence score (0-1).")


class ParseResponse(BaseModel):
    questions: List[QuestionAnswerItem] = Field(
        default_factory=list, description="Structured questionnaire results."
    )
    raw_text: str = Field(
        ..., description="Raw OCR text as returned by OpenAI before structuring."
    )
    debug_blocks: Optional[List[ParserDebugBlock]] = Field(
        default=None,
        description="Optional debug data for diagnostics when enabled.",
    )
