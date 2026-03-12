"""LLM client factory used across the project."""

from functools import lru_cache

from anthropic import Anthropic

from config.settings import get_settings


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    """Return a cached Anthropic client."""

    settings = get_settings()
    return Anthropic(api_key=settings.api_key)
