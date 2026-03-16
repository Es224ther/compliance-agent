from __future__ import annotations

from typing import Any, Literal

from app.rag.kb.vector_store import get_default_store


def semantic_search(
    query: str,
    jurisdiction: Literal["EU", "CN", "All"] = "All",
    n_results: int = 10,
    tag_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Semantic retrieval against Chroma collections."""
    top_n = max(1, n_results)
    store = get_default_store()
    query_embedding = store.embed_query(query)

    where_filter: dict[str, Any] = {}
    if jurisdiction in {"EU", "CN"}:
        where_filter["jurisdiction"] = jurisdiction

    candidates = store.query(
        embedding=query_embedding,
        n_results=max(top_n * 3, 30),
        filter=where_filter or None,
    )

    if tag_filter:
        wanted = {tag.strip() for tag in tag_filter if tag.strip()}
        filtered: list[dict[str, Any]] = []
        for item in candidates:
            tags_value = item.get("tags", "")
            if isinstance(tags_value, str):
                tags = {tag.strip() for tag in tags_value.split(",") if tag.strip()}
            elif isinstance(tags_value, list):
                tags = {str(tag).strip() for tag in tags_value if str(tag).strip()}
            else:
                tags = set()
            if wanted.issubset(tags):
                filtered.append(item)
        # Only apply tag filter if it leaves enough candidates; otherwise fall back.
        if len(filtered) >= top_n:
            candidates = filtered

    output: list[dict[str, Any]] = []
    for item in candidates[:top_n]:
        copied = dict(item)
        copied["distance"] = _to_float_or_none(item.get("distance"))
        output.append(copied)
    return output


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

