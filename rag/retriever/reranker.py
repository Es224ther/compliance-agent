from __future__ import annotations

import re
from typing import Any


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    limit = max(1, top_k)
    if not candidates:
        return []

    scorer = _RerankModel.get()
    scored: list[dict[str, Any]] = []
    for item in candidates:
        text = str(item.get("search_text") or item.get("text") or "")
        score = float(scorer.score(query, text))
        copied = dict(item)
        copied["rerank_score"] = score
        if score < 0.6:
            copied["low_confidence"] = True
        scored.append(copied)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:limit]


class _RerankModel:
    _instance: "_RerankModel | None" = None

    @classmethod
    def get(cls) -> "_RerankModel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._cross_encoder = None
        try:
            from sentence_transformers import CrossEncoder  # type: ignore

            self._cross_encoder = CrossEncoder("BAAI/bge-reranker-v2-m3")
        except Exception:
            self._cross_encoder = None

    def score(self, query: str, text: str) -> float:
        if self._cross_encoder is not None:
            value = self._cross_encoder.predict([(query, text)])
            return _to_float(value[0])
        return _fallback_overlap_score(query, text)


def _fallback_overlap_score(query: str, text: str) -> float:
    q_tokens = _tokenize(query)
    t_tokens = _tokenize(text)
    if not q_tokens or not t_tokens:
        return 0.0
    inter = len(q_tokens.intersection(t_tokens))
    denom = max(1, len(q_tokens))
    return min(1.0, inter / denom)


def _tokenize(value: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", value.lower())
    return {tok for tok in tokens if tok.strip()}


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

