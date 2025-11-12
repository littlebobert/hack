"""Application settings and configuration helpers."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Top-level application configuration."""

    openai_api_key: str | None = Field(
        default=None,
        description="API key used for communicating with OpenAI.",
    )
    openai_model: str = Field(
        default=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        description="OpenAI model used for OCR/vision parsing.",
    )
    request_timeout_seconds: float = Field(
        default=float(os.getenv("OPENAI_TIMEOUT", "45")),
        description="Timeout for OpenAI requests.",
    )
    max_image_megabytes: int = Field(
        default=int(os.getenv("MAX_IMAGE_MB", "10")),
        description="Maximum upload size accepted by the API.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings(openai_api_key=os.getenv("OPENAI_API_KEY"))
