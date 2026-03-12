"""Pydantic models for tool input and output payloads."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scenario import NormalizedScenario


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


# ---------------------------------------------------------------------------
# 1. Retrieval tool
# ---------------------------------------------------------------------------


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    query: str
    regulations: Optional[List[str]] = None
    jurisdictions: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1)


class RegulationChunk(BaseModel):
    model_config = ConfigDict(strict=False)

    text: str
    regulation: str
    article: str
    jurisdiction: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(strict=False)

    chunks: List[RegulationChunk]


# ---------------------------------------------------------------------------
# 2. Risk scoring tool
# ---------------------------------------------------------------------------


class RiskItem(BaseModel):
    model_config = ConfigDict(strict=False)

    category: str
    level: RiskLevel
    description: str
    remediation: str
    owner: str
    regulation_refs: List[str]


class RiskScoringRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    scenario: NormalizedScenario
    chunks: List[RegulationChunk]


class RiskScoringResult(BaseModel):
    model_config = ConfigDict(strict=False)

    risk_items: List[RiskItem]


# ---------------------------------------------------------------------------
# 3. Remediation tool
# ---------------------------------------------------------------------------


class RemediationAction(BaseModel):
    model_config = ConfigDict(strict=False)

    action: str
    priority: Priority
    owner: str
    deadline_hint: str


class RemediationRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    risk_items: List[RiskItem]


class RemediationResult(BaseModel):
    model_config = ConfigDict(strict=False)

    actions: List[RemediationAction]
