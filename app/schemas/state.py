"""Shared pipeline state models for Compliance Agent."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scenario import ParsedFields, ScenarioInput


class SharedState(BaseModel):
    """Container carried across the compliance analysis pipeline."""

    model_config = ConfigDict(strict=False)

    raw_input: ScenarioInput
    parsed_fields: ParsedFields = Field(default_factory=ParsedFields)
    pii_map: dict[str, Any] = Field(default_factory=dict)
    followup_rounds: int = 0
    followup_prompt: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    risk_level: str | None = None
    evidence: list[str] = Field(default_factory=list)
    report: dict[str, Any] | None = None
