"""Application settings, loaded from the .env file in the project root."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-3.6-flash")
    max_history_turns: int = Field(default=10)
    session_ttl_minutes: int = Field(default=60)
    port: int = Field(default=8000)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Copy .env.example to .env and put your "
            "key in it. Get one at https://aistudio.google.com/apikey"
        )
    return settings


settings = get_settings()
