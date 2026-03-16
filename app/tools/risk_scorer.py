"""Deterministic rule-based risk scorer."""

from __future__ import annotations

from typing import Any

from app.schemas.evidence import EvidenceChunk
from app.schemas.risk import RiskLevel
from app.schemas.scenario import ParsedFields

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

    risk_overview = _generate_human_readable_overview(
        parsed_fields=parsed_fields,
        final_level=current_level,
        scoring_factors=scoring_factors,
        evidence_chunks=evidence,
    )
    return current_level, risk_overview, scoring_factors


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


def build_risk_debug_trace(
    evidence: list[EvidenceChunk],
    final_level: RiskLevel,
    scoring_factors: list[dict[str, Any]],
) -> str:
    """Build developer-facing debug trace for scoring diagnostics."""

    base_level = _detect_base_level(_normalize_evidence(evidence))
    return _build_debug_summary(base_level, final_level, scoring_factors)


def _build_debug_summary(
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


def _generate_human_readable_overview(
    parsed_fields: ParsedFields,
    final_level: RiskLevel,
    scoring_factors: list[dict[str, Any]],
    evidence_chunks: list[EvidenceChunk],
) -> str:
    parts: list[str] = []
    data_types = parsed_fields.data_types or []

    if "Biometric" in data_types:
        parts.append("涉及生物特征数据（如人脸信息）的处理")
    elif "Personal" in data_types:
        parts.append("涉及个人数据处理")
    elif data_types:
        parts.append(f"涉及{'、'.join(data_types)}数据处理")

    if parsed_fields.cross_border:
        parts.append("数据存在跨境传输")
    if parsed_fields.third_party_model:
        parts.append("涉及第三方模型服务")
    if parsed_fields.aigc_output:
        parts.append("存在面向用户的 AI 生成内容输出")

    rule_descriptions = {
        "biometric_force_critical": "生物特征数据处理触发了特殊类别数据保护要求",
        "cross_border_plus_third_party": "跨境传输叠加第三方处理提高了合规风险",
        "aigc_cn_regulation": "AIGC 场景触发了额外透明度与标识义务",
        "dual_jurisdiction_complexity": "双法域并行义务提高了治理复杂度",
    }
    for factor in scoring_factors:
        rule = str(factor.get("rule", ""))
        description = rule_descriptions.get(rule)
        if description:
            parts.append(description)

    regulations = sorted({chunk.regulation for chunk in evidence_chunks if chunk.regulation})
    if regulations:
        parts.append(f"涉及 {'/'.join(regulations)} 等法规要求")

    if not parts:
        parts.append("当前证据显示存在基础合规义务")

    return "本场景" + "，".join(parts) + f"，综合风险等级为 {final_level.value}。"
