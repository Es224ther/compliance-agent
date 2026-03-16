"""Confidence guardrails for evidence quality checks."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceChunk
from app.schemas.scenario import ParsedFields


class ConfidenceResult(BaseModel):
    model_config = ConfigDict(strict=False)

    low_confidence: bool
    reason: str | None = None
    triggered_conditions: list[str] = Field(default_factory=list)


def check_jurisdiction_completeness(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields,
) -> bool:
    if parsed_fields.region != "EU+CN":
        return True
    jurisdictions = {
        str(chunk.jurisdiction).upper()
        for chunk in evidence
        if str(chunk.jurisdiction).upper() in {"EU", "CN"}
    }
    return jurisdictions == {"EU", "CN"}


def evaluate_confidence(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields,
) -> ConfidenceResult:
    triggered: list[str] = []
    reasons: list[str] = []

    if not evidence:
        triggered.append("all_scores_below_threshold")
        reasons.append("未检索到法规证据")
    else:
        if all((chunk.rerank_score or 0.0) < 0.6 for chunk in evidence):
            triggered.append("all_scores_below_threshold")
            reasons.append("全部证据 rerank_score 低于 0.6")

        top3 = sorted(evidence, key=lambda c: c.rerank_score or 0.0, reverse=True)[:3]
        regulations = {chunk.regulation for chunk in top3}
        if len(top3) == 3 and len(regulations) == 3:
            tag_lists = [set(chunk.tags) for chunk in top3]
            overlap = tag_lists[0].intersection(tag_lists[1], tag_lists[2])
            if not overlap:
                triggered.append("top3_regulations_disjoint_tags")
                reasons.append("Top-3 证据来自不同法规且标签无交集")

    missing_fields = parsed_fields.missing_fields or []
    if len(missing_fields) >= 2:
        triggered.append("missing_fields_ge_2")
        reasons.append(f"关键字段缺失较多: {', '.join(missing_fields)}")

    if not check_jurisdiction_completeness(evidence, parsed_fields):
        triggered.append("eu_cn_single_jurisdiction")
        reasons.append("EU+CN 场景仅检索到单一法域证据")

    low_confidence = bool(triggered)
    reason = reasons[0] if reasons else None
    if len(reasons) > 1:
        reason = "；".join(reasons)
    return ConfidenceResult(
        low_confidence=low_confidence,
        reason=reason,
        triggered_conditions=triggered,
    )
