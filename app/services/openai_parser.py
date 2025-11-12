"""Questionnaire parsing via OpenAI's OCR-capable APIs."""

from __future__ import annotations

import base64
import json
from contextlib import suppress
from typing import Any, Dict, Optional

from fastapi import UploadFile

from ..schemas import ParseResponse, ParserDebugBlock, QuestionAnswerItem

try:  # pragma: no cover - external dependency
    from openai import OpenAI
    from openai import APIConnectionError, APIStatusError, OpenAIError
except Exception as exc:  # pragma: no cover - surfaces during import failures
    raise ImportError(
        "The `openai` package is required. Install it via `pip install openai`."
    ) from exc


RESPONSE_SCHEMA: Dict[str, Any] = {
    "name": "questionnaire_ocr",
    "schema": {
        "type": "object",
        "properties": {
            "raw_text": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                    "required": ["question", "answer"],
                    "additionalProperties": False,
                },
                "default": [],
            },
            "debug_blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["line", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["raw_text", "questions"],
        "additionalProperties": False,
    },
}


class ParserError(Exception):
    """Raised whenever questionnaire parsing fails."""


class OpenAIQuestionnaireParser:
    """Encapsulates OpenAI OCR calls and result shaping."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout: float,
        max_image_megabytes: int,
    ) -> None:
        if not api_key:
            raise ParserError(
                "OPENAI_API_KEY is not configured. Set it before using the API."
            )

        self.model = model
        self.timeout = timeout
        self.max_bytes = max_image_megabytes * 1024 * 1024
        self.client = OpenAI(api_key=api_key, timeout=timeout)

    async def parse_upload(
        self, file: UploadFile, *, include_debug: bool = False
    ) -> ParseResponse:
        """Parse questionnaire from an uploaded file."""
        image_bytes = await file.read()
        if not image_bytes:
            raise ParserError("Uploaded file is empty.")

        if len(image_bytes) > self.max_bytes:
            raise ParserError(
                f"Uploaded file exceeds {self.max_bytes // (1024 * 1024)} MB limit."
            )

        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = self._request_openai(base64_image, include_debug=include_debug)
        return self._to_response(payload, include_debug=include_debug)

    def _request_openai(self, image_base64: str, *, include_debug: bool) -> Dict[str, Any]:
        """Call OpenAI Responses API and return parsed JSON payload."""
        prompt = self._build_prompt(include_debug=include_debug)
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an OCR specialist that extracts questionnaire data. "
                                    "Always output concise text without commentary."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_base64": image_base64},
                        ],
                    },
                ],
                response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
                max_output_tokens=900,
            )
        except (APIConnectionError, APIStatusError) as exc:
            raise ParserError("Failed to contact OpenAI. Try again later.") from exc
        except OpenAIError as exc:
            raise ParserError(str(exc)) from exc

        json_payload = self._extract_json(response)
        if not isinstance(json_payload, dict):
            raise ParserError("Unexpected OpenAI response format.")
        return json_payload

    @staticmethod
    def _build_prompt(*, include_debug: bool) -> str:
        base_prompt = (
            "Read the questionnaire image and extract every question and its answer. "
            "Normalize answers by concatenating checkboxes or handwritten text. "
            "If an answer is blank, use an empty string. "
            "Return the transcription text in `raw_text`.\n"
        )
        if include_debug:
            base_prompt += (
                "Provide up to 15 `debug_blocks` entries summarizing lines you observed "
                "with a confidence value between 0 and 1."
            )
        else:
            base_prompt += "You may omit `debug_blocks` when not relevant."
        return base_prompt

    @staticmethod
    def _extract_json(response: Any) -> Dict[str, Any]:
        """Extract JSON string from OpenAI response object."""
        # Responses API returns `output` -> content -> text
        try:
            for item in response.output:
                contents = getattr(item, "content", None)
                if contents is None and isinstance(item, dict):
                    contents = item.get("content", [])
                if not contents:
                    continue
                for content in contents:
                    content_type = getattr(content, "type", None)
                    text_value = getattr(content, "text", None)
                    if content_type is None and isinstance(content, dict):
                        content_type = content.get("type")
                        text_value = text_value or content.get("text")
                    if content_type in {"output_text", "text"} and text_value:
                        return json.loads(text_value)
        except AttributeError:
            pass

        # Fallback to choices (legacy)
        with suppress(Exception):
            choices = getattr(response, "choices")
            if choices:
                message = choices[0].message
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    return json.loads(content)

        raise ParserError("Unable to parse JSON from OpenAI response.")

    @staticmethod
    def _to_response(
        payload: Dict[str, Any],
        *,
        include_debug: bool,
    ) -> ParseResponse:
        """Convert OpenAI JSON payload into ParseResponse."""
        questions = [
            QuestionAnswerItem(
                question=str(item.get("question", "")).strip(),
                answer=str(item.get("answer", "")).strip(),
            )
            for item in payload.get("questions", [])
            if item
        ]

        debug_blocks = None
        if include_debug:
            debug_blocks = [
                ParserDebugBlock(
                    line=str(block.get("line", "")),
                    confidence=float(block.get("confidence", 0)),
                )
                for block in payload.get("debug_blocks", [])
                if block
            ]

        raw_text = str(payload.get("raw_text", "")).strip()
        return ParseResponse(
            questions=questions,
            raw_text=raw_text,
            debug_blocks=debug_blocks,
        )
