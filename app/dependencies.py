"""Dependency injection helpers for FastAPI."""

from functools import lru_cache

from .core import get_settings
from .services.openai_parser import OpenAIQuestionnaireParser


@lru_cache
def _build_parser() -> OpenAIQuestionnaireParser:
    settings = get_settings()
    return OpenAIQuestionnaireParser(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout=settings.request_timeout_seconds,
        max_image_megabytes=settings.max_image_megabytes,
    )


def get_parser_service() -> OpenAIQuestionnaireParser:
    """Return singleton parser service."""
    return _build_parser()
