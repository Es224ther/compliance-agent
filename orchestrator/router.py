"""Region router used to plan jurisdiction retrieval coverage."""

from __future__ import annotations

from typing import Literal

from schemas.scenario import ParsedFields

CN_KEYWORDS = ["国内", "中国", "境内", "传回国内", "国内服务器", "回国", "中国境内"]
EU_KEYWORDS = ["欧洲", "EU", "欧盟", "GDPR", "欧洲用户"]


def determine_jurisdictions(parsed_fields: ParsedFields, raw_text: str) -> set[Literal["EU", "CN"]]:
    """Determine retrieval jurisdictions from parsed fields and raw text."""

    jurisdictions: set[Literal["EU", "CN"]] = set()

    region = parsed_fields.region or ""
    if "EU" in region or region == "Global":
        jurisdictions.add("EU")
    if "CN" in region or region == "Global":
        jurisdictions.add("CN")

    if any(keyword in raw_text for keyword in CN_KEYWORDS):
        jurisdictions.add("CN")
    if any(keyword in raw_text for keyword in EU_KEYWORDS):
        jurisdictions.add("EU")

    if parsed_fields.cross_border and len(jurisdictions) < 2:
        if "EU" in jurisdictions and "CN" not in jurisdictions:
            jurisdictions.add("CN")
        elif "CN" in jurisdictions and "EU" not in jurisdictions:
            jurisdictions.add("EU")

    if not jurisdictions:
        return {"EU", "CN"}
    return jurisdictions


def jurisdictions_to_region(
    jurisdictions: set[Literal["EU", "CN"]],
    fallback_region: str | None = None,
) -> Literal["EU", "CN", "EU+CN", "Global"] | None:
    """Convert jurisdiction set back to canonical region field values."""

    if jurisdictions == {"EU", "CN"}:
        return "EU+CN"
    if jurisdictions == {"EU"}:
        return "EU"
    if jurisdictions == {"CN"}:
        return "CN"
    if fallback_region in {"EU", "CN", "EU+CN", "Global"}:
        return fallback_region
    return "Global"


def route_by_region(
    parsed_fields: ParsedFields,
    raw_text: str = "",
) -> list[Literal["EU", "CN"]]:
    """Backward-compatible helper returning deterministic retrieval order."""

    jurisdictions = determine_jurisdictions(parsed_fields, raw_text)
    return [j for j in ("EU", "CN") if j in jurisdictions]
