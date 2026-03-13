"""Deterministic rule-based risk scorer."""

from __future__ import annotations

from typing import Any

from schemas.evidence import EvidenceChunk
from schemas.risk import RiskLevel
from schemas.scenario import ParsedFields

_LEVEL_ORDER = [
    RiskLevel.LOW,
    RiskLevel.MEDIUM,
    RiskLevel.HIGH,
    RiskLevel.CRITICAL,
]

_CRITICAL_KEYWORDS = [
    "biometric",
    "生物特征",
    "人脸识别",
    "adequacy decision",
    "数据出境安全评估",
    "standard contractual clauses",
]
_HIGH_KEYWORDS = [
    "cross-border transfer",
    "third country",
    "跨境传输",
    "数据出境",
]
_MEDIUM_KEYWORDS = [
    "consent",
    "同意",
    "transparency",
    "透明度",
    "告知",
]


def calculate_risk_level(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields,
) -> tuple[RiskLevel, str, list[dict[str, Any]]]:
    """Return deterministic risk level, summary and applied scoring factors."""

    normalized_blob = _normalize_evidence(evidence)
    base_level = _detect_base_level(normalized_blob)
    current_level = base_level
    scoring_factors: list[dict[str, Any]] = []

    if parsed_fields.cross_border is True and parsed_fields.third_party_model is True:
        current_level = _bump_level(current_level)
        scoring_factors.append(
            {
                "rule": "cross_border_plus_third_party",
                "description": "Cross-border transfer with third-party model usage",
                "impact": "+1 level (capped at Critical)",
            }
        )

    if "Biometric" in (parsed_fields.data_types or []):
        current_level = RiskLevel.CRITICAL
        scoring_factors.append(
            {
                "rule": "biometric_force_critical",
                "description": "Biometric data present → force Critical",
                "impact": "force Critical",
            }
        )

    region = parsed_fields.region or ""
    if parsed_fields.aigc_output is True and "CN" in region:
        current_level = _bump_level(current_level)
        scoring_factors.append(
            {
                "rule": "aigc_cn_regulation",
                "description": "AIGC output in CN jurisdiction → stronger regulation",
                "impact": "+1 level (capped at Critical)",
            }
        )

    if parsed_fields.region == "EU+CN":
        current_level = _bump_level(current_level)
        scoring_factors.append(
            {
                "rule": "dual_jurisdiction_complexity",
                "description": "Region EU+CN → +1 complexity adjustment",
                "impact": "+1 level (capped at Critical)",
            }
        )

    summary = _build_summary(base_level, current_level, scoring_factors)
    return current_level, summary, scoring_factors


def _normalize_evidence(evidence: list[EvidenceChunk]) -> str:
    parts: list[str] = []
    for chunk in evidence:
        parts.extend(
            [
                chunk.regulation,
                chunk.article,
                chunk.text,
                chunk.summary or "",
            ]
        )
    return " ".join(parts).lower()


def _detect_base_level(normalized_blob: str) -> RiskLevel:
    if any(keyword in normalized_blob for keyword in _CRITICAL_KEYWORDS):
        return RiskLevel.CRITICAL
    if any(keyword in normalized_blob for keyword in _HIGH_KEYWORDS):
        return RiskLevel.HIGH
    if any(keyword in normalized_blob for keyword in _MEDIUM_KEYWORDS):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _bump_level(level: RiskLevel) -> RiskLevel:
    index = _LEVEL_ORDER.index(level)
    if index >= len(_LEVEL_ORDER) - 1:
        return RiskLevel.CRITICAL
    return _LEVEL_ORDER[index + 1]


def _build_summary(
    base_level: RiskLevel,
    final_level: RiskLevel,
    scoring_factors: list[dict[str, Any]],
) -> str:
    if not scoring_factors:
        return f"Base level {base_level.value}; no additional adjustment rules were triggered."
    rules = ", ".join(str(item.get("rule", "")) for item in scoring_factors)
    return (
        f"Base level {base_level.value}; triggered rules: {rules}; "
        f"final level {final_level.value}."
    )
