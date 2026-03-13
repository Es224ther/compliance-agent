from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


EN_ARTICLE_RE = re.compile(r"\bArticle\s+(\d+)\b", flags=re.I)
EN_ART_SHORT_RE = re.compile(r"\bArt\.\s*(\d+)\b", flags=re.I)
EN_PARAGRAPH_RE = re.compile(r"\bparagraph\s+(\d+)\b", flags=re.I)
CN_ARTICLE_RE = re.compile(r"第([零〇一二三四五六七八九十百两\d]+)条")
CN_THIS_LAW_RE = re.compile(r"(?:本法第|依据第)([零〇一二三四五六七八九十百两\d]+)条")

DEFAULT_GRAPH_PATH = Path("data/kb/cross_ref_graph.json")


def enrich_chunks_with_cross_refs(
    chunks: list[dict[str, Any]],
    *,
    graph_path: str | Path = DEFAULT_GRAPH_PATH,
) -> list[dict[str, Any]]:
    article_index = _build_article_index(chunks)
    graph: dict[str, list[str]] = {}
    enriched: list[dict[str, Any]] = []

    for chunk in chunks:
        regulation = str(chunk.get("regulation", "")).strip()
        text = str(chunk.get("text", ""))
        refs = extract_cross_refs(text, regulation=regulation)

        copied = dict(chunk)
        copied["cross_refs"] = refs
        enriched.append(copied)

        targets: list[str] = []
        for ref in refs:
            number = _extract_number_from_ref_article_id(ref["article_id"])
            if number is None:
                continue
            target_chunk_id = article_index.get((regulation, number))
            if target_chunk_id:
                targets.append(target_chunk_id)

        graph[str(chunk.get("chunk_id", ""))] = _dedupe(targets)

    _save_graph(Path(graph_path), graph)
    return enriched


def extract_cross_refs(text: str, *, regulation: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []

    for match in EN_ARTICLE_RE.finditer(text):
        refs.append(
            {
                "regulation": regulation,
                "article_id": f"Article {int(match.group(1))}",
                "ref_type": "cites",
            }
        )
    for match in EN_ART_SHORT_RE.finditer(text):
        refs.append(
            {
                "regulation": regulation,
                "article_id": f"Article {int(match.group(1))}",
                "ref_type": "cites",
            }
        )
    for match in EN_PARAGRAPH_RE.finditer(text):
        refs.append(
            {
                "regulation": regulation,
                "article_id": f"paragraph {int(match.group(1))}",
                "ref_type": "cites",
            }
        )

    for match in CN_ARTICLE_RE.finditer(text):
        refs.append(
            {
                "regulation": regulation,
                "article_id": f"第{match.group(1)}条",
                "ref_type": "cites",
            }
        )
    for match in CN_THIS_LAW_RE.finditer(text):
        refs.append(
            {
                "regulation": regulation,
                "article_id": f"第{match.group(1)}条",
                "ref_type": "cites",
            }
        )

    return _dedupe_ref_objects(refs)


def _build_article_index(chunks: list[dict[str, Any]]) -> dict[tuple[str, int], str]:
    index: dict[tuple[str, int], str] = {}
    for chunk in chunks:
        regulation = str(chunk.get("regulation", "")).strip()
        article_id = str(chunk.get("article_id", "")).strip()
        chunk_id = str(chunk.get("chunk_id", "")).strip()
        number = _extract_number_from_chunk_article_id(article_id)
        if number is None or not chunk_id:
            continue
        key = (regulation, number)
        index.setdefault(key, chunk_id)
    return index


def _extract_number_from_chunk_article_id(article_id: str) -> int | None:
    eu = re.match(r"^Article(?:\s+|_)(\d+)(?:_\d+)?$", article_id, flags=re.I)
    if eu:
        return int(eu.group(1))

    cn = re.match(r"^第([零〇一二三四五六七八九十百两\d]+)条(?:_\d+)?$", article_id)
    if cn:
        raw = cn.group(1)
        if raw.isdigit():
            return int(raw)
        return _cn_numeral_to_int(raw)
    return None


def _extract_number_from_ref_article_id(article_id: str) -> int | None:
    eu = re.match(r"^Article\s+(\d+)$", article_id, flags=re.I)
    if eu:
        return int(eu.group(1))
    cn = re.match(r"^第([零〇一二三四五六七八九十百两\d]+)条$", article_id)
    if cn:
        raw = cn.group(1)
        if raw.isdigit():
            return int(raw)
        return _cn_numeral_to_int(raw)
    return None


def _cn_numeral_to_int(text: str) -> int:
    text = text.replace("〇", "零").replace("两", "二")
    digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100}
    if text.isdigit():
        return int(text)

    total = 0
    current = 0
    for ch in text:
        if ch in digits:
            current = digits[ch]
        elif ch in units:
            if current == 0:
                current = 1
            total += current * units[ch]
            current = 0
    total += current
    return total


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _dedupe_ref_objects(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, str]] = []
    for ref in refs:
        key = (ref["regulation"], ref["article_id"], ref["ref_type"])
        if key in seen:
            continue
        seen.add(key)
        output.append(ref)
    return output


def _save_graph(path: Path, graph: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

