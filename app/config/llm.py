"""LLM client factory used across the project."""

from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from app.config.settings import get_settings


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Return a cached OpenAI-compatible client."""

    settings = get_settings()
    return OpenAI(
        api_key=settings.api_key,
        base_url=settings.openai_base_url,
    )


@lru_cache(maxsize=1)
def get_async_client() -> AsyncOpenAI:
    """Return a cached async OpenAI-compatible client."""

    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.openai_base_url,
    )
