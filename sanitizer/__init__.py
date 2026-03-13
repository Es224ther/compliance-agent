"""Local PII sanitization package."""

from __future__ import annotations

from sanitizer.anonymizer import PIIAnonymizer
from sanitizer.engine import SanitizerEngine
from sanitizer.pii_map import InMemoryPiiMap

_default_anonymizer = PIIAnonymizer()


def anonymize(text: str) -> tuple[str, dict[str, str]]:
    language = "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "en"
    return _default_anonymizer.anonymize(text=text, language=language)

__all__ = [
    "InMemoryPiiMap",
    "PIIAnonymizer",
    "SanitizerEngine",
    "anonymize",
]
