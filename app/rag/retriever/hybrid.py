from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from app.schemas import ParsedFields
from app.schemas.evidence import EvidenceChunk
from app.rag.retriever.keyword import keyword_search
from app.rag.retriever.reranker import rerank
from app.rag.retriever.semantic import semantic_search


def hybrid_search(
    query: str,
    parsed_fields: ParsedFields,
    top_k: int = 5,
) -> list[EvidenceChunk]:
    jurisdiction = _region_to_jurisdiction(parsed_fields.region)
    tag_filter = _extract_tag_filter(parsed_fields)

    with ThreadPoolExecutor(max_workers=2) as pool:
        semantic_future = pool.submit(
            semantic_search,
            query,
            jurisdiction,
            10,
            tag_filter if tag_filter else None,
        )
        keyword_future = pool.submit(keyword_search, query, jurisdiction, 10)
        semantic_hits = semantic_future.result()
        keyword_hits = keyword_future.result()

    merged = _merge_candidates(semantic_hits, keyword_hits, limit=20)
    ranked = rerank(query=query, candidates=merged, top_k=max(1, top_k))
    return [_to_evidence_chunk(item) for item in ranked]


def _region_to_jurisdiction(region: str | None) -> Literal["EU", "CN", "All"]:
    if region == "EU":
        return "EU"
    if region == "CN":
        return "CN"
    return "All"


def _extract_tag_filter(parsed_fields: ParsedFields) -> list[str]:
    tags: list[str] = []
    if parsed_fields.cross_border:
        tags.append("cross_border_transfer")
    if parsed_fields.third_party_model:
        tags.append("third_party")
    if parsed_fields.aigc_output:
        tags.append("aigc")

    for data_type in parsed_fields.data_types or []:
        if data_type == "Biometric":
            tags.append("biometric")
    return _dedupe(tags)


def _merge_candidates(
    semantic_hits: list[dict],
    keyword_hits: list[dict],
    *,
    limit: int,
) -> list[dict]:
    merged: dict[str, dict] = {}

    for item in semantic_hits + keyword_hits:
        chunk_id = str(item.get("chunk_id", ""))
        if not chunk_id:
            continue
        if chunk_id not in merged:
            merged[chunk_id] = dict(item)
            continue
        existing = merged[chunk_id]
        for key in ("distance", "bm25_score"):
            new_value = item.get(key)
            old_value = existing.get(key)
            if old_value is None:
                existing[key] = new_value
            elif new_value is not None:
                if key == "distance":
                    existing[key] = min(float(old_value), float(new_value))
                else:
                    existing[key] = max(float(old_value), float(new_value))

    return list(merged.values())[:limit]


def _to_evidence_chunk(item: dict) -> EvidenceChunk:
    tags = item.get("tags", [])
    if isinstance(tags, str):
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    elif isinstance(tags, list):
        tag_list = [str(tag).strip() for tag in tags if str(tag).strip()]
    else:
        tag_list = []

    return EvidenceChunk(
        chunk_id=str(item.get("chunk_id", "")),
        regulation=str(item.get("regulation", "")),
        jurisdiction=str(item.get("jurisdiction", "")),
        language=str(item.get("language", "")) if item.get("language") is not None else None,
        article_id=str(item.get("article_id", "")),
        article_title=str(item.get("article_title", "")) if item.get("article_title") is not None else None,
        chapter=str(item.get("chapter", "")) if item.get("chapter") is not None else None,
        text=str(item.get("text", "")),
        tags=tag_list,
        summary=str(item.get("summary", "")) if item.get("summary") is not None else None,
        distance=_to_float_or_none(item.get("distance")),
        bm25_score=_to_float_or_none(item.get("bm25_score")),
        rerank_score=_to_float_or_none(item.get("rerank_score")),
        low_confidence=bool(item.get("low_confidence", False)),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _to_float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

