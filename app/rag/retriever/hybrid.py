from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from app.schemas import ParsedFields
from app.schemas.evidence import EvidenceChunk
from app.rag.retriever.keyword import keyword_search
from app.rag.retriever.reranker import rerank
from app.rag.retriever.semantic import semantic_search


# Bilingual term dictionary for cross-lingual query augmentation.
_ZH_TO_EN: list[tuple[str, str]] = [
    ("跨境", "cross-border transfer GDPR standard contractual clauses"),
    ("出境", "cross-border transfer"),
    ("第三方", "third-party processor"),
    ("委托处理", "data processor agreement"),
    ("个人信息", "personal data GDPR"),
    ("同意", "consent"),
    ("生物特征", "biometric data"),
    ("人脸", "facial recognition biometric"),
    ("透明度", "transparency obligations"),
    ("生成内容", "AI-generated content"),
    ("标识", "labeling disclosure"),
    ("数据处理", "data processing"),
    ("数据传输", "data transfer"),
    ("敏感", "sensitive personal information"),
    ("合规", "compliance"),
    ("协议", "agreement contract"),
    ("用户数据", "personal data GDPR"),
]

_EN_TO_ZH: list[tuple[str, str]] = [
    ("cross-border", "跨境传输"),
    ("transfer", "数据传输"),
    ("third party", "第三方委托处理"),
    ("third-party", "第三方委托处理"),
    ("entrust", "委托处理"),
    ("processor", "数据处理者"),
    ("personal data", "个人信息"),
    ("personal information", "个人信息"),
    ("consent", "同意"),
    ("biometric", "生物特征"),
    ("transparency", "透明度"),
    ("ai-generated", "AI生成内容"),
    ("ai generated", "AI生成内容"),
    ("labeling", "标识"),
    ("disclosure", "披露标识"),
    ("sensitive", "敏感信息"),
]


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _augment_query_cross_lingual(query: str, jurisdiction: str) -> str:
    """Append bilingual keywords to improve reranker cross-lingual scoring."""
    is_cjk = _contains_cjk(query)

    # Chinese query searching EU (English) regulations
    if is_cjk and jurisdiction == "EU":
        supplements: list[str] = []
        for zh_term, en_term in _ZH_TO_EN:
            if zh_term in query:
                supplements.append(en_term)
        if supplements:
            return f"{query} ({', '.join(supplements)})"

    # English query searching CN (Chinese) regulations
    if not is_cjk and jurisdiction == "CN":
        query_lower = query.lower()
        # Split into words for stem-level matching (handles plurals etc.)
        query_words = set(re.findall(r"[a-z]+", query_lower))
        supplements = []
        for en_term, zh_term in _EN_TO_ZH:
            # Check phrase match first, then fall back to stem-word overlap.
            if en_term in query_lower:
                supplements.append(zh_term)
            else:
                en_words = set(en_term.split())
                if en_words and all(any(qw.startswith(ew) or ew.startswith(qw) for qw in query_words) for ew in en_words):
                    supplements.append(zh_term)
        if supplements:
            return f"{query} ({', '.join(supplements)})"

    return query


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

    # Augment query for cross-lingual reranking.
    rerank_query = _augment_query_cross_lingual(query, jurisdiction)
    ranked = rerank(query=rerank_query, candidates=merged, top_k=max(1, top_k))
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

    # Expose merged article IDs so callers can match against absorbed short articles.
    merged_raw = item.get("merged_article_ids", "")
    if isinstance(merged_raw, str) and merged_raw.strip():
        merged_ids = [mid.strip() for mid in merged_raw.split(",") if mid.strip()]
    elif isinstance(merged_raw, list):
        merged_ids = [str(mid).strip() for mid in merged_raw if str(mid).strip()]
    else:
        merged_ids = []

    chunk = EvidenceChunk(
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
    # Attach merged IDs as extra attribute for downstream matching.
    chunk._merged_article_ids = merged_ids  # type: ignore[attr-defined]
    return chunk


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

