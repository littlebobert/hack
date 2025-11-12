from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message
from pydantic import ValidationError

from ..config import Settings
from ..schemas import FieldType, FormDocument

SYSTEM_PROMPT = """You are a meticulous document understanding assistant. Always return machine-consumable JSON that matches the provided schema exactly, and include bounding boxes (normalized 0-1 floats) for every field. Estimate coordinates when in doubt."""

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


def _collect_text(response: Message) -> str:
    parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)


async def extract_form_from_image(
    image_b64: str,
    file_name: str,
    settings: Settings,
    storage_path: str,
) -> FormDocument:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    media_type = "image/jpeg"
    if "." in file_name:
        ext = file_name.rsplit(".", 1)[-1].lower()
        if ext in {"png", "webp"}:
            media_type = f"image/{ext}"

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_TEMPLATE},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                ],
            }
        ],
    )

    json_payload = _collect_text(response)
    raw_response_dir = Path("storage/debug")
    raw_response_dir.mkdir(parents=True, exist_ok=True)
    response_path = raw_response_dir / f"{uuid.uuid4().hex}_anthropic_raw.json"
    response_path.write_text(json_payload)

    cleaned_payload = json_payload.strip()
    if cleaned_payload.startswith("```"):
        cleaned_payload = cleaned_payload.strip("`")
        if cleaned_payload.startswith("json"):
            cleaned_payload = cleaned_payload[4:]
        cleaned_payload = cleaned_payload.strip()
    if not cleaned_payload.startswith("{") or not cleaned_payload.endswith("}"):
        start = cleaned_payload.find("{")
        end = cleaned_payload.rfind("}")
        if start != -1 and end != -1:
            cleaned_payload = cleaned_payload[start : end + 1]

    try:
        parsed: dict[str, Any] = json.loads(cleaned_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from Anthropic response: {exc}") from exc

    parsed.setdefault("form_id", uuid.uuid4().hex)
    parsed.setdefault("title", file_name.rsplit(".", 1)[0] if "." in file_name else file_name)
    parsed.setdefault("description", None)
    parsed.setdefault("version", "1.0.0")
    parsed.setdefault("created_at", datetime.utcnow().isoformat())
    parsed["source_image_url"] = storage_path

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
                bbox = None
        else:
            field.pop("bounding_box", None)
            bbox = None

        if bbox is None:
            fallback_height = max(0.03, 1.0 / max(len(fields), 1))
            fallback_y = min(0.95, index * fallback_height)
            if field_type == "checkbox":
                fallback_box = {
                    "x": 0.72,
                    "y": fallback_y,
                    "width": 0.25,
                    "height": fallback_height,
                }
            else:
                fallback_box = {
                    "x": 0.5,
                    "y": fallback_y,
                    "width": 0.45,
                    "height": fallback_height,
                }
            field["bounding_box"] = fallback_box

        normalized_fields.append(field)

    parsed["fields"] = normalized_fields

    try:
        return FormDocument.model_validate(parsed)
    except ValidationError as exc:
        logging.exception("Failed to validate Anthropic form payload: %s", exc)
        raise ValueError(f"Form validation failed: {exc}") from exc

