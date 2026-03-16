from __future__ import annotations

from typing import Any


_TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("cross_border_transfer", ("cross-border", "transfer", "third country", "跨境", "出境")),
    ("consent", ("consent", "同意")),
    ("biometric", ("biometric", "生物特征", "人脸", "敏感个人信息")),
    ("ai_governance", ("artificial intelligence", "人工智能", " ai ")),
    ("aigc", ("generate", "synthetic", "生成", "合成", "标识", "声明")),
    ("third_party", ("third party", "第三方")),
    ("risk_assessment", ("assessment", "评估", "dpia")),
]


def infer_tags(text: str) -> list[str]:
    source = f" {text.lower()} "
    original = text
    tags: list[str] = []
    for tag, keywords in _TAG_RULES:
        if any(_contains_keyword(source, original, keyword) for keyword in keywords):
            tags.append(tag)
    return tags


def enrich_chunks_with_tags(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for chunk in chunks:
        content = " ".join(
            str(chunk.get(key, ""))
            for key in ("regulation", "article_id", "article_title", "chapter", "text")
        )
        copied = dict(chunk)
        copied["tags"] = infer_tags(content)
        enriched.append(copied)
    return enriched


def _contains_keyword(source_lower: str, source_original: str, keyword: str) -> bool:
    if any("\u4e00" <= ch <= "\u9fff" for ch in keyword):
        return keyword in source_original
    return keyword.lower() in source_lower

