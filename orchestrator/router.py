"""Region router used to plan jurisdiction retrieval coverage."""

from __future__ import annotations

from typing import Literal

from schemas.scenario import ParsedFields


def route_by_region(parsed_fields: ParsedFields) -> list[Literal["EU", "CN"]]:
    if parsed_fields.region == "EU":
        return ["EU"]
    if parsed_fields.region == "CN":
        return ["CN"]
    if parsed_fields.region in {"EU+CN", "Global", None}:
        return ["EU", "CN"]
    return ["EU", "CN"]
