"""Validation helpers for intake agent tool output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.schemas import ParsedFields


@dataclass(slots=True)
class SchemaValidationResult:
    """Validated parsed fields and the list of invalid field names."""

    parsed_fields: ParsedFields
    invalid_fields: list[str]


FIELD_ADAPTERS = {
    field_name: TypeAdapter(field_info.annotation)
    for field_name, field_info in ParsedFields.model_fields.items()
}
STRICT_BOOL_FIELDS = {"cross_border", "third_party_model", "aigc_output"}


def validate_parse_scenario_output(payload: dict[str, Any]) -> SchemaValidationResult:
    """Validate each parse_scenario field independently and null invalid values."""

    sanitized: dict[str, Any] = {}
    invalid_fields: list[str] = []

    for field_name in ParsedFields.model_fields:
        raw_value = payload.get(field_name)
        if raw_value is None:
            sanitized[field_name] = None
            continue

        if field_name in STRICT_BOOL_FIELDS and not isinstance(raw_value, bool):
            sanitized[field_name] = None
            invalid_fields.append(field_name)
            continue

        try:
            sanitized[field_name] = FIELD_ADAPTERS[field_name].validate_python(raw_value)
        except ValidationError:
            sanitized[field_name] = None
            invalid_fields.append(field_name)

    # Post-processing: Biometric/Financial/Behavioral imply Personal.
    dt = sanitized.get("data_types")
    if isinstance(dt, list) and dt:
        implies_personal = {"Biometric", "Financial", "Behavioral"}
        if any(t in implies_personal for t in dt) and "Personal" not in dt:
            sanitized["data_types"] = ["Personal"] + dt

    return SchemaValidationResult(
        parsed_fields=ParsedFields(**sanitized),
        invalid_fields=invalid_fields,
    )
