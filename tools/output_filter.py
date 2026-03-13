"""Tone-softening filter for generated report fields."""

from __future__ import annotations

from typing import Iterable

from observability.logger import log_json_event
from schemas.report import AuditReport

FILTERABLE_FIELDS = {
    "summary",
    "risk_overview",
    "uncertainties",
    "remediation_actions",
    "reasoning",
}

PROTECTED_FIELDS = {
    "evidence_citations",
    "disclaimer",
}

REPLACEMENTS = {
    "贵司必须": "建议贵司",
    "违法": "可能不符合相关法规要求",
    "违规": "存在合规风险",
    "必须立即": "建议尽快",
    "严重违反": "可能违反",
    "必须遵守": "需关注",
    "must immediately": "should prioritize",
    "strictly prohibited": "generally not recommended",
    "must": "should consider",
    "illegal": "potentially non-compliant",
}


def filter_report_fields(report: AuditReport) -> AuditReport:
    filtered = report.model_copy(deep=True)

    filtered.summary = _replace_text("summary", filtered.summary)
    filtered.risk_overview = _replace_text("risk_overview", filtered.risk_overview)
    filtered.reasoning = _replace_text("reasoning", filtered.reasoning)
    filtered.uncertainties = [
        _replace_text("uncertainties", item) for item in filtered.uncertainties
    ]

    for action in filtered.remediation_actions:
        action.action = _replace_text("remediation_actions", action.action)
    return filtered


def _replace_text(field: str, value: str) -> str:
    updated = value
    for source in _replacement_order():
        target = REPLACEMENTS[source]
        if source not in updated:
            continue
        replaced = updated.replace(source, target)
        log_json_event(
            {
                "field": field,
                "original": updated,
                "filtered": replaced,
                "rule": source,
            }
        )
        updated = replaced
    return updated


def _replacement_order() -> Iterable[str]:
    return sorted(REPLACEMENTS, key=len, reverse=True)
