from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str
    anthropic_model: str = "claude-3-haiku-20240307"
    app_env: str = "development"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8081",
            "http://localhost:8082",
            "http://localhost:3000",
            "http://localhost:19006",
            "exp://127.0.0.1:19000",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FORMBUILDER_",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Optional[str | list[str]]) -> list[str]:
        if value is None:
            return cls.model_fields["allowed_origins"].default_factory()  # type: ignore[return-value]
        if isinstance(value, str):
            entries = [item.strip().strip('"').strip("'") for item in value.strip("[]").split(",") if item.strip()]
            return entries or cls.model_fields["allowed_origins"].default_factory()  # type: ignore[return-value]
        return list(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()

