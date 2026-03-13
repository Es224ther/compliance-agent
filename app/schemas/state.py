"""Shared pipeline state models for Compliance Agent."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence import EvidenceChunk
from app.schemas.report import AuditReport
from app.schemas.risk import EscalationResult, RiskAssessment
from app.schemas.scenario import ParsedFields, ScenarioInput, generate_session_id


class PipelineStatus(str, Enum):
    CREATED = "CREATED"
    SANITIZING = "SANITIZING"
    PARSING = "PARSING"
    AWAITING_FOLLOWUP = "AWAITING_FOLLOWUP"
    RETRIEVING = "RETRIEVING"
    ANALYZING = "ANALYZING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SharedState(BaseModel):
    """Container carried across the compliance analysis pipeline."""

    model_config = ConfigDict(strict=False)

    session_id: str | None = None
    raw_input: ScenarioInput | None = None
    status: PipelineStatus = PipelineStatus.CREATED
    parsed_fields: ParsedFields = Field(default_factory=ParsedFields)
    pii_map: dict[str, Any] = Field(default_factory=dict)
    followup_rounds: int = 0
    followup_prompt: str | None = None
    followup_questions: list[str] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    risk_level: str | None = None
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    escalation_result: EscalationResult | None = None
    report: AuditReport | dict[str, Any] | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _ensure_session_id(self) -> "SharedState":
        if self.session_id:
            return self
        if self.raw_input and self.raw_input.session_id:
            self.session_id = self.raw_input.session_id
        else:
            self.session_id = generate_session_id()
        return self
