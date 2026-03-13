"""Pydantic model for the final structured compliance report."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceChunk
from app.schemas.risk import EscalationResult, RemediationAction, RiskLevel
from app.schemas.scenario import ParsedFields


class AuditReport(BaseModel):
    """Five-section report format required by Day3."""

    model_config = ConfigDict(strict=False)

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: str

    summary: str
    risk_level: RiskLevel
    risk_overview: str
    evidence_citations: list[EvidenceChunk]
    uncertainties: list[str]
    remediation_actions: list[RemediationAction]

    parsed_fields: ParsedFields
    jurisdictions_covered: list[Literal["EU", "CN"]]
    requires_escalation: bool
    escalation_result: EscalationResult | None
    disclaimer: str
    reasoning: str = ""

    def to_markdown(self) -> str:
        evidence_lines = [
            f"- [{chunk.regulation} {chunk.article}] {chunk.summary or chunk.text}"
            for chunk in self.evidence_citations
        ]
        uncertainty_lines = [f"- {item}" for item in self.uncertainties] or ["- 无"]
        remediation_lines = [
            f"- [{action.role}/{action.priority}] {action.action}（{action.regulation_ref}）"
            for action in self.remediation_actions
        ]
        sections = [
            self.disclaimer.strip(),
            "## 场景摘要",
            self.summary.strip(),
            "## 风险等级",
            f"- 等级：{self.risk_level.value}",
            f"- 概述：{self.risk_overview.strip()}",
            "## 法规证据",
            "\n".join(evidence_lines) if evidence_lines else "- 无",
            "## 不确定项",
            "\n".join(uncertainty_lines),
            "## 整改建议",
            "\n".join(remediation_lines) if remediation_lines else "- 无",
            self.disclaimer.strip(),
        ]
        return "\n\n".join(sections)

    def to_json(self) -> dict:
        return self.model_dump(mode="json")
