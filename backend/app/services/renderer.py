from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any, List

from PIL import Image, ImageDraw, ImageFont

from ..schemas import FieldType, FormDocument


def render_filled_form(document: FormDocument, values: dict[str, Any]) -> str:
    if not document.source_image_url:
        raise ValueError("Form document does not include a source image path.")

    image_path = Path(document.source_image_url)
    if not image_path.exists():
        raise ValueError(f"Source image not found at {image_path}")

    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)

    width, height = image.size

    for field in document.fields:
        bbox = field.bounding_box
        if not bbox:
            continue

        value = values.get(field.id)
        if isinstance(value, str) and not value.strip():
            continue
        if value is None and field.type != FieldType.checkbox:
            continue

        x = int(max(0.0, min(1.0, bbox.x)) * width)
        y = int(max(0.0, min(1.0, bbox.y)) * height)
        w = max(2, int(max(0.0, min(1.0, bbox.width)) * width))
        h = max(2, int(max(0.0, min(1.0, bbox.height)) * height))

        if field.type in {
            FieldType.text,
            FieldType.textarea,
            FieldType.date,
            FieldType.select,
            FieldType.signature,
        }:
            text_value = _stringify_value(value)
            if w > width * 0.5:
                padding_x = int(w * 0.45)
            else:
                padding_x = max(4, int(w * 0.05))
            available_width = max(10, w - padding_x * 2)

            font_size = max(12, min(int(h * 0.6), 40))
            field_font = _load_font(font_size)
            line_height = _line_height(field_font)

            lines = _wrap_text(text_value, field_font, available_width)
            total_height = len(lines) * (line_height + 2)
            start_y = max(y + 4, y + (h - total_height) / 2)
            for idx, line in enumerate(lines):
                baseline = start_y + idx * (line_height + 2)
                if baseline > y + h - line_height:
                    break
                draw.text(
                    (x + padding_x, baseline),
                    line,
                    fill=(20, 20, 20),
                    font=field_font,
                    stroke_width=2,
                    stroke_fill=(255, 255, 255),
                )

        elif field.type == FieldType.checkbox:
            box_side = max(12, int(min(w, h, 36)))
            if w > width * 0.4:
                checkbox_x = x + w * 0.7
            else:
                checkbox_x = x
            checkbox_y = y + max(0, (h - box_side) / 2)
            checkbox_rect = [checkbox_x, checkbox_y, checkbox_x + box_side, checkbox_y + box_side]
            draw.rectangle(checkbox_rect, outline=(55, 55, 55), width=2)
            if bool(value):
                draw.line(
                    (
                        checkbox_x + box_side * 0.2,
                        checkbox_y + box_side * 0.55,
                        checkbox_x + box_side * 0.45,
                        checkbox_y + box_side * 0.8,
                    ),
                    fill=(55, 55, 55),
                    width=4,
                )
                draw.line(
                    (
                        checkbox_x + box_side * 0.45,
                        checkbox_y + box_side * 0.8,
                        checkbox_x + box_side * 0.8,
                        checkbox_y + box_side * 0.2,
                    ),
                    fill=(55, 55, 55),
                    width=4,
                )

        elif field.type == FieldType.table:
            # For now, add a subtle highlight to denote captured data.
            draw.rectangle([x, y, x + w, y + h], outline=(55, 55, 55), width=2)

    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded


def _load_font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("Arial.ttf", size=size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    if not text:
        return [""]

    lines: List[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.getlength(candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _stringify_value(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(_stringify_value(item) for item in value)
    return str(value)


def _line_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ag")
    return bbox[3] - bbox[1]

