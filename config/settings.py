"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings for the Compliance Agent."""

    api_key: str = Field(..., alias="API_KEY")
    model_name: str = Field(
        default="claude-sonnet-4-20250514",
        alias="MODEL_NAME",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
        strict=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
