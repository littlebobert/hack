from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, List, Optional


class FieldType(str, Enum):
    text = "text"
    textarea = "textarea"
    checkbox = "checkbox"
    select = "select"
    date = "date"
    signature = "signature"
    table = "table"


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1, description="Relative x position (0-1)")
    y: float = Field(ge=0, le=1, description="Relative y position (0-1)")
    width: float = Field(ge=0, le=1, description="Relative width (0-1)")
    height: float = Field(ge=0, le=1, description="Relative height (0-1)")


class FormField(BaseModel):
    id: str
    label: str
    type: FieldType
    bounding_box: Optional[BoundingBox] = None
    options: Optional[List[str]] = None
    required: bool = False
    placeholder: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FormDocument(BaseModel):
    form_id: str
    title: str
    description: Optional[str] = None
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fields: List[FormField]
    source_image_url: Optional[str] = None


class ExtractionRequest(BaseModel):
    file_name: str


class ExtractionResponse(BaseModel):
    document: FormDocument

