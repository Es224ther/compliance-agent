"""Pydantic models representing compliance scenario inputs and parsed fields."""

from enum import Enum
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def generate_session_id() -> str:
    """Generate a stable string session identifier."""

    return str(uuid4())


class ScenarioInput(BaseModel):
    """Raw scenario text submitted into the pipeline."""

    model_config = ConfigDict(strict=False)

    raw_text: str
    session_id: str = Field(default_factory=generate_session_id)


class ParsedFields(BaseModel):
    """Structured fields extracted from a raw scenario."""

    model_config = ConfigDict(strict=False)

    region: Literal["EU", "CN", "Global", "EU+CN"] | None = None
    data_types: (
        list[Literal["Personal", "Behavioral", "Biometric", "Financial"]] | None
    ) = None
    cross_border: bool | None = None
    third_party_model: bool | None = None
    aigc_output: bool | None = None
    data_volume_level: Literal["Small", "Medium", "Large"] | None = None
    missing_fields: list[str] | None = None


class DataRegion(str, Enum):
    CN = "CN"
    EU = "EU"
    US = "US"
    UK = "UK"
    GLOBAL = "GLOBAL"


class DataType(str, Enum):
    personal = "personal"
    sensitive = "sensitive"
    behavioral = "behavioral"
    financial = "financial"
    location = "location"
    biometric = "biometric"
    minor = "minor"


class ProcessingPurpose(str, Enum):
    model_training = "model_training"
    model_inference = "model_inference"
    analytics = "analytics"
    personalization = "personalization"
    safety = "safety"
    legal_compliance = "legal_compliance"


class NormalizedScenario(BaseModel):
    model_config = ConfigDict(strict=False)

    scenario_id: str
    raw_description: str
    product_name: Optional[str] = None
    user_regions: List[DataRegion]
    cross_border_transfer: bool
    transfer_destination: Optional[List[DataRegion]] = None
    data_types: List[DataType]
    involves_minors: bool
    involves_sensitive_data: bool
    processing_purposes: List[ProcessingPurpose]
    uses_third_party_model: bool
    third_party_providers: Optional[List[str]] = None
    data_shared_with_third_party: bool
    has_user_consent: Optional[bool] = None
    has_privacy_notice: Optional[bool] = None
    data_retention_defined: Optional[bool] = None
    submitted_by: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    clarification_needed: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_transfer_destination(self) -> "NormalizedScenario":
        if self.cross_border_transfer and not self.transfer_destination:
            raise ValueError(
                "transfer_destination must be provided when cross_border_transfer is True"
            )
        return self

    @model_validator(mode="after")
    def check_involves_minors_flag(self) -> "NormalizedScenario":
        if DataType.minor in self.data_types and not self.involves_minors:
            raise ValueError(
                "involves_minors must be True when DataType.minor is present in data_types"
            )
        return self

    @model_validator(mode="after")
    def check_involves_sensitive_flag(self) -> "NormalizedScenario":
        sensitive_types = {
            DataType.sensitive,
            DataType.biometric,
            DataType.financial,
            DataType.location,
        }
        if sensitive_types.intersection(self.data_types) and not self.involves_sensitive_data:
            raise ValueError(
                "involves_sensitive_data must be True when sensitive data types are present"
            )
        return self
