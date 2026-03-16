"""Placeholder-based anonymization for local PII masking."""

from typing import Any

from app.sanitizer.engine import SanitizerEngine
from app.sanitizer.pii_map import InMemoryPiiMap

DEFAULT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CN_PHONE", "CN_ID"]


class PIIAnonymizer:
    """Replace detected PII spans with stable placeholders."""

    def __init__(self, engine: SanitizerEngine | None = None) -> None:
        self.engine = engine or SanitizerEngine()

    def anonymize(
        self,
        text: str,
        language: str,
        entities: list[str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Return masked text and its in-memory placeholder mapping."""

        results = self.engine.analyze(
            text=text,
            language=language,
            entities=entities or DEFAULT_ENTITIES,
        )
        resolved_results = self._resolve_overlaps(results)
        pii_map = InMemoryPiiMap()

        parts: list[str] = []
        cursor = 0
        for result in resolved_results:
            original = text[result.start : result.end]
            placeholder = pii_map.add(result.entity_type, original)
            parts.append(text[cursor : result.start])
            parts.append(placeholder)
            cursor = result.end

        parts.append(text[cursor:])
        return "".join(parts), pii_map.to_dict()

    @staticmethod
    def _resolve_overlaps(results: list[Any]) -> list[Any]:
        ordered = sorted(
            results,
            key=lambda item: (item.start, -(item.end - item.start), -item.score),
        )

        resolved: list[Any] = []
        last_end = -1
        for result in ordered:
            if result.start < last_end:
                continue
            resolved.append(result)
            last_end = result.end
        return resolved
