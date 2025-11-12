from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: Optional[HttpUrl] = None
    app_env: str = "development"
    allowed_origins: list[str] = ["http://localhost:8081", "http://localhost:3000", "exp://127.0.0.1:19000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FORMBUILDER_",
    )

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

