"""LLM client factory used across the project."""

from functools import lru_cache

from anthropic import Anthropic, AsyncAnthropic

from config.settings import get_settings


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    """Return a cached Anthropic client."""

    settings = get_settings()
    return Anthropic(api_key=settings.api_key)


@lru_cache(maxsize=1)
def get_async_client() -> AsyncAnthropic:
    """Return a cached async Anthropic client."""

    settings = get_settings()
    return AsyncAnthropic(api_key=settings.api_key)
