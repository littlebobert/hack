from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from ..config import Settings
from ..schemas import FieldType, FormDocument

PROMPT_TEMPLATE = """You are an assistant that converts scanned or photographed paper forms into structured JSON.
Analyze the provided form image and return a JSON object that follows this TypeScript type:

type FormDocument = {{
  form_id: string;
  title: string;
  description?: string;
  version: string;
  created_at: string; // ISO datetime
  source_image_url?: string;
  fields: Array<{
    id: string;
    label: string;
    type: "text" | "textarea" | "checkbox" | "select" | "date" | "signature" | "table";
    required: boolean;
    placeholder?: string;
    options?: string[];
    bounding_box?: {{ x: number; y: number; width: number; height: number }}; // All values between 0 and 1 relative to page
    metadata?: Record<string, any>;
  }>;
}};

Guidelines:
- Carefully read field labels, checkboxes, tables, and signature lines.
- Provide unique, stable ids for each field using snake_case.
- Use table type for tabular sections, include metadata.table_headers for column names.
- Include bounding_box where possible with normalized coordinates.
- The description field can summarize instructions shown on the form.
- Only include fields the user must fill. Ignore decorative elements.
- Ensure the JSON is valid and matches the schema exactly. Do not wrap in markdown."""


async def extract_form_from_image(
    image_b64: str,
    file_name: str,
    settings: Settings,
    storage_path: str,
) -> FormDocument:
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=str(settings.openai_base_url) if settings.openai_base_url else None,
    )

    response = await client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT_TEMPLATE},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/{file_name.split('.')[-1].lower() if '.' in file_name else 'jpeg'};base64,{image_b64}",
                    }
                ],
            }
        ],
        temperature=0.1,
        max_output_tokens=2048,
    )

    try:
        json_payload = response.output_text  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise ValueError("Unexpected response format from OpenAI API.") from exc

    try:
        parsed: dict[str, Any] = json.loads(json_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from OpenAI response: {exc}") from exc

    parsed.setdefault("form_id", uuid.uuid4().hex)
    parsed.setdefault("title", file_name.rsplit(".", 1)[0] if "." in file_name else file_name)
    parsed.setdefault("description", None)
    parsed.setdefault("version", "1.0.0")
    parsed.setdefault("created_at", datetime.utcnow().isoformat())
    parsed.setdefault("source_image_url", storage_path)

    fields = parsed.get("fields", [])
    if not isinstance(fields, list):
        fields = []

    normalized_fields: list[dict[str, Any]] = []
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            continue
        field = field.copy()
        field.setdefault("id", f"field_{index+1}")
        field.setdefault("label", field["id"].replace("_", " ").title())

        field_type = str(field.get("type", "text")).lower()
        if field_type not in {ft.value for ft in FieldType}:
            field_type = "text"
        field["type"] = field_type

        field["required"] = False
        if field_type == "select" and isinstance(field.get("options"), list):
            field["options"] = [str(option) for option in field["options"]]

        metadata = field.get("metadata")
        if not isinstance(metadata, dict):
            field["metadata"] = {}

        bbox = field.get("bounding_box")
        if isinstance(bbox, dict):
            try:
                normalized_bbox = {
                    key: max(0.0, min(1.0, float(bbox.get(key, 0))))
                    for key in ("x", "y", "width", "height")
                }
                field["bounding_box"] = normalized_bbox
            except (TypeError, ValueError):
                field.pop("bounding_box", None)

        normalized_fields.append(field)

    parsed["fields"] = normalized_fields

    try:
        return FormDocument.model_validate(parsed)
    except ValidationError as exc:
        logging.exception("Failed to validate OpenAI form payload: %s", exc)
        raise ValueError(f"Form validation failed: {exc}") from exc

