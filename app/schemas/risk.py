"""Risk assessment schemas used by the Day3 pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence import EvidenceChunk


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class RemediationAction(BaseModel):
    model_config = ConfigDict(strict=False)

    role: Literal["PM", "Dev", "Security"]
    action: str
    priority: Literal["Immediate", "Short-term", "Long-term"]
    regulation_ref: str


class EscalationResult(BaseModel):
    model_config = ConfigDict(strict=False)

    requires_escalation: bool = False
    reasons: list[str] = Field(default_factory=list)
    primary_reason: str = ""

    @model_validator(mode="after")
    def _fill_primary_reason(self) -> "EscalationResult":
        if self.reasons and not self.primary_reason:
            self.primary_reason = self.reasons[0]
        if not self.reasons and self.primary_reason:
            self.reasons = [self.primary_reason]
        return self


class RiskAssessment(BaseModel):
    model_config = ConfigDict(strict=False)

    risk_level: RiskLevel
    risk_summary: str
    reasoning: str
    jurisdictions_covered: list[Literal["EU", "CN"]] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    remediation: list[RemediationAction] = Field(default_factory=list)
    low_confidence_items: list[str] = Field(default_factory=list)
    requires_escalation: bool = False
    scoring_factors: list[dict[str, Any]] = Field(default_factory=list)
