"""Lightweight PII detection engine based on regex heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.sanitizer.cn_id_card import CN_ID_PATTERN

EMAIL_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9._%+-])[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}(?![a-z0-9._%+-])"
)
CN_PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")


@dataclass(slots=True)
class DetectionResult:
    entity_type: str
    start: int
    end: int
    score: float


class SanitizerEngine:
    """Regex-first sanitizer implementation for deterministic local tests."""

    def __init__(self) -> None:
        self._fallback_mode = True
        self.zh_ner_available = False
        self.en_ner_available = False

    def analyze(
        self,
        text: str,
        language: str,
        entities: list[str] | None = None,
    ) -> list[DetectionResult]:
        requested = set(entities or ["EMAIL_ADDRESS", "CN_PHONE", "CN_ID"])
        results: list[DetectionResult] = []

        if "EMAIL_ADDRESS" in requested:
            results.extend(
                DetectionResult(
                    entity_type="EMAIL_ADDRESS",
                    start=match.start(),
                    end=match.end(),
                    score=0.85,
                )
                for match in EMAIL_PATTERN.finditer(text)
            )

        if "CN_PHONE" in requested:
            results.extend(
                DetectionResult(
                    entity_type="CN_PHONE",
                    start=match.start(),
                    end=match.end(),
                    score=0.85,
                )
                for match in CN_PHONE_PATTERN.finditer(text)
            )

        if "CN_ID" in requested:
            results.extend(
                DetectionResult(
                    entity_type="CN_ID",
                    start=match.start(1),
                    end=match.end(1),
                    score=0.95,
                )
                for match in CN_ID_PATTERN.finditer(text)
            )

        return sorted(results, key=lambda item: (item.start, item.end))
