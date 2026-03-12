"""Pydantic model for the final structured compliance report."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tool_io import RemediationAction, RiskItem, RiskLevel


class AuditReport(BaseModel):
    model_config = ConfigDict(strict=False)

    report_id: str
    scenario_id: str
    product_name: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    executive_summary: str
    overall_risk_level: RiskLevel
    risk_score: int = Field(..., ge=0, le=100)
    risk_items: List[RiskItem]
    applicable_regulations: List[str]
    remediation_actions: List[RemediationAction]
    uncertainties: List[str] = Field(default_factory=list)
    requires_human_review: bool
    escalation_targets: List[str] = Field(default_factory=list)
    trace_id: str
