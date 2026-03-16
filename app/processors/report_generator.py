"""Audit report generation orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.guards import legal_disclaimer
from app.guards.field_rules import generate_uncertainties
from app.schemas.evidence import EvidenceChunk
from app.schemas.report import AuditReport
from app.schemas.risk import EscalationResult, RiskAssessment
from app.schemas.state import SharedState
from app.tools import output_filter

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "templates" / "report.txt"


async def generate_report(
    state: SharedState,
    risk_assessment: RiskAssessment,
    escalation_result: EscalationResult,
) -> AuditReport:
    # The prompt text is loaded to keep runtime behavior aligned with prompt-driven design.
    _ = PROMPT_PATH.read_text(encoding="utf-8")

    parsed_fields = state.parsed_fields
    raw_text = state.raw_input.raw_text if state.raw_input else ""
    generated_uncertainties = generate_uncertainties(parsed_fields, raw_text)
    uncertainties = _dedupe_preserve_order(
        list(risk_assessment.low_confidence_items) + generated_uncertainties
    )

    report_payload = {
        "session_id": state.session_id or "unknown",
        "summary": _build_summary(state),
        "risk_level": risk_assessment.risk_level,
        "risk_overview": risk_assessment.risk_summary,
        "evidence_citations": trim_evidence_for_report(risk_assessment.evidence),
        "uncertainties": uncertainties,
        "remediation_actions": risk_assessment.remediation,
        "parsed_fields": parsed_fields,
        "jurisdictions_covered": risk_assessment.jurisdictions_covered,
        "requires_escalation": escalation_result.requires_escalation,
        "escalation_result": escalation_result,
        "disclaimer": "",
        "reasoning": risk_assessment.reasoning,
    }
    if state.report_id:
        report_payload["report_id"] = state.report_id

    try:
        report = AuditReport.model_validate(report_payload)
    except ValidationError as exc:
        report_payload["requires_escalation"] = True
        report_payload["uncertainties"] = uncertainties + [
            f"报告结构校验失败：{exc.errors()[0]['msg']}"
        ]
        report = AuditReport.model_validate(report_payload)

    report = output_filter.filter_report_fields(report)
    report = legal_disclaimer.inject_disclaimer(report)
    return report


def _build_summary(state: SharedState) -> str:
    parsed = state.parsed_fields
    data_types_cn = {
        "Personal": "个人数据",
        "Biometric": "生物特征数据",
        "Behavioral": "行为数据",
        "Financial": "金融数据",
    }

    types = [data_types_cn.get(data_type, data_type) for data_type in (parsed.data_types or [])]
    types_str = "、".join(types) if types else "未明确数据类型"

    region_desc = {
        "EU": "欧盟",
        "CN": "中国",
        "EU+CN": "欧盟与中国",
        "Global": "全球多法域",
    }.get(parsed.region, parsed.region or "未确定法域")

    cross_border_desc = "涉及跨境数据传输" if parsed.cross_border else "暂未识别跨境传输"
    third_party_desc = (
        "涉及第三方模型调用"
        if parsed.third_party_model
        else ("第三方模型调用尚不明确" if parsed.third_party_model is None else "不涉及第三方模型调用")
    )
    aigc_desc = (
        "包含面向用户的 AI 生成内容输出"
        if parsed.aigc_output
        else ("AIGC 输出状态尚不明确" if parsed.aigc_output is None else "不涉及面向用户的 AIGC 输出")
    )

    summary = (
        f"本场景涉及{types_str}处理，覆盖{region_desc}法域，{cross_border_desc}，"
        f"{third_party_desc}，{aigc_desc}。"
    )
    return _clean_summary(summary)


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _clean_summary(summary: str) -> str:
    cleaned = summary.replace("。。", "。").replace("..", ".").replace("  ", " ").strip()
    while "。。" in cleaned:
        cleaned = cleaned.replace("。。", "。")
    if len(cleaned) > 100:
        cleaned = cleaned[:100].rstrip("，。") + "。"
    return cleaned


def trim_evidence_for_report(raw_evidence: list[EvidenceChunk | dict[str, Any]]) -> list[EvidenceChunk]:
    """Return compact evidence objects for report payloads."""

    trimmed: list[EvidenceChunk] = []
    for evidence in raw_evidence:
        source = evidence.model_dump() if isinstance(evidence, EvidenceChunk) else dict(evidence)
        text = str(source.get("text", "") or "")
        summary = str(source.get("summary", "") or "").strip() or _fallback_summary(text)
        tags = source.get("tags", [])
        if not isinstance(tags, list):
            tags = [tag.strip() for tag in str(tags).split(",") if tag.strip()]

        trimmed.append(
            EvidenceChunk(
                regulation=str(source.get("regulation", "")),
                article=str(source.get("article_id") or source.get("article") or ""),
                jurisdiction=str(source.get("jurisdiction", "")),
                text=_truncate_text(text, max_len=200),
                summary=summary,
                rerank_score=source.get("rerank_score"),
                tags=[str(tag) for tag in tags],
                chunk_id=str(source.get("chunk_id", "") or ""),
                language=(
                    str(source.get("language"))
                    if source.get("language") not in (None, "")
                    else None
                ),
                article_id=(
                    str(source.get("article_id"))
                    if source.get("article_id") not in (None, "")
                    else None
                ),
                article_title=(
                    str(source.get("article_title"))
                    if source.get("article_title") not in (None, "")
                    else None
                ),
                chapter=(
                    str(source.get("chapter"))
                    if source.get("chapter") not in (None, "")
                    else None
                ),
                distance=source.get("distance"),
                bm25_score=source.get("bm25_score"),
                low_confidence=bool(source.get("low_confidence", False)),
            )
        )
    return trimmed


def _fallback_summary(text: str, max_len: int = 200) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 20]
    content = " ".join(lines[:3]) if lines else text.strip()
    if len(content) > max_len:
        return content[: max_len - 3] + "..."
    return content


def _truncate_text(text: str, max_len: int = 200) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 20]
    content = " ".join(lines[:4]) if lines else text.strip()
    if len(content) > max_len:
        return content[: max_len - 3] + "..."
    return content


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output
