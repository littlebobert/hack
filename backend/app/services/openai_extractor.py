from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from ..config import Settings
from ..schemas import FormDocument

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
                        "image_base64": image_b64,
                        "image_format": file_name.split(".")[-1].lower() if "." in file_name else "jpeg",
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
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

    if "source_image_url" not in parsed:
        parsed["source_image_url"] = storage_path

    return FormDocument.model_validate(parsed)

