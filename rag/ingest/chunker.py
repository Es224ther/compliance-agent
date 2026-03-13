from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_META_BLOCK_RE = re.compile(r"<!--(.*?)-->", flags=re.S)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_EU_ARTICLE_RE = re.compile(r"^Article\s+(\d+)\s*:\s*(.+)$", flags=re.I)
_CN_ARTICLE_RE = re.compile(r"^(第[零〇一二三四五六七八九十百两\d]+条)\s*(.*)$")
_CN_ARTICLE_ID_RE = re.compile(r"^第([零〇一二三四五六七八九十百两\d]+)条$")
_EU_ARTICLE_ID_RE = re.compile(r"^Article\s+(\d+)$", flags=re.I)
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


@dataclass
class ParsedArticle:
    article_id: str
    article_title: str
    chapter: str
    text: str


def chunk_regulation(
    file_path: str | Path,
    *,
    long_article_threshold: int = 800,
    short_article_threshold: int = 50,
    merge_short_articles: bool = True,
) -> list[dict[str, Any]]:
    source_path = Path(file_path)
    raw_text = source_path.read_text(encoding="utf-8")
    metadata = _parse_metadata(raw_text)
    content = _strip_meta_block(raw_text)

    parsed_articles = _parse_articles(content)
    chunks: list[dict[str, Any]] = []
    regulation_prefix = _regulation_prefix(source_path.name)

    for article in parsed_articles:
        article_no = _extract_article_number(article.article_id)
        if article_no is None:
            article_key = _slugify(article.article_id)
            base_chunk_id = f"{regulation_prefix}_art_{article_key}"
        else:
            base_chunk_id = f"{regulation_prefix}_art{article_no}"

        token_count = estimate_token_count(article.text)
        if token_count <= long_article_threshold:
            chunks.append(
                _build_chunk(
                    base_chunk_id=base_chunk_id,
                    metadata=metadata,
                    article_id=article.article_id,
                    article_title=article.article_title,
                    chapter=article.chapter,
                    text=article.text,
                )
            )
            continue

        parts = _split_long_article(article.text)
        normalized_id = _normalize_article_id_for_subchunks(article.article_id, article_no)
        for idx, part in enumerate(parts, start=1):
            sub_chunk_id = f"{base_chunk_id}_p{idx}"
            sub_article_id = f"{normalized_id}_{idx}"
            chunks.append(
                _build_chunk(
                    base_chunk_id=sub_chunk_id,
                    metadata=metadata,
                    article_id=sub_article_id,
                    article_title=article.article_title,
                    chapter=article.chapter,
                    text=part,
                )
            )

    if merge_short_articles and short_article_threshold > 0:
        chunks = _merge_short_chunks(chunks, min_tokens=short_article_threshold)

    return chunks


def estimate_token_count(text: str) -> int:
    words = len(_WORD_RE.findall(text))
    cjk_chars = len(_CJK_RE.findall(text))
    return words + cjk_chars


def _parse_metadata(raw_text: str) -> dict[str, str]:
    match = _META_BLOCK_RE.search(raw_text)
    if not match:
        return {
            "regulation": "",
            "jurisdiction": "",
            "language": "",
        }
    block = match.group(1)
    result: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return {
        "regulation": result.get("regulation", ""),
        "jurisdiction": result.get("jurisdiction", ""),
        "language": result.get("language", ""),
    }


def _strip_meta_block(raw_text: str) -> str:
    return _META_BLOCK_RE.sub("", raw_text, count=1).lstrip()


def _parse_articles(content: str) -> list[ParsedArticle]:
    lines = content.splitlines()
    articles: list[ParsedArticle] = []

    current_chapter = ""
    current_article_id: str | None = None
    current_article_title = ""
    current_article_chapter = ""
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_article_id, current_article_title, current_article_chapter, current_lines
        if current_article_id is None:
            return
        text = "\n".join(line for line in current_lines if line.strip()).strip()
        articles.append(
            ParsedArticle(
                article_id=current_article_id,
                article_title=current_article_title,
                chapter=current_article_chapter,
                text=text,
            )
        )
        current_article_id = None
        current_article_title = ""
        current_article_chapter = ""
        current_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            if current_article_id is not None:
                current_lines.append("")
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            heading_text = heading_match.group(2).strip()
            article_info = _parse_article_heading(heading_text)
            if article_info is None:
                current_chapter = heading_text
                continue
            flush_current()
            current_article_id, current_article_title = article_info
            current_article_chapter = current_chapter
            continue

        if current_article_id is not None:
            current_lines.append(line.strip())

    flush_current()
    return articles


def _parse_article_heading(heading_text: str) -> tuple[str, str] | None:
    eu_match = _EU_ARTICLE_RE.match(heading_text)
    if eu_match:
        article_no = eu_match.group(1)
        article_title = eu_match.group(2).strip()
        return f"Article {article_no}", article_title

    cn_match = _CN_ARTICLE_RE.match(heading_text)
    if cn_match:
        article_id = cn_match.group(1)
        article_title = cn_match.group(2).strip()
        if not article_title:
            article_title = article_id
        return article_id, article_title
    return None


def _split_long_article(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    if not paragraphs:
        return [text]

    max_tokens = 800
    parts: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        p_tokens = estimate_token_count(paragraph)
        if current_lines and current_tokens + p_tokens > max_tokens:
            parts.append("\n".join(current_lines).strip())
            current_lines = [paragraph]
            current_tokens = p_tokens
            continue
        current_lines.append(paragraph)
        current_tokens += p_tokens

    if current_lines:
        parts.append("\n".join(current_lines).strip())
    return parts


def _merge_short_chunks(chunks: list[dict[str, Any]], *, min_tokens: int) -> list[dict[str, Any]]:
    if not chunks:
        return chunks

    merged: list[dict[str, Any]] = []
    idx = 0
    while idx < len(chunks):
        chunk = chunks[idx]
        if chunk["token_count"] >= min_tokens:
            merged.append(chunk)
            idx += 1
            continue

        if merged:
            prev = merged[-1]
            prev["text"] = f"{prev['text']}\n{chunk['text']}".strip()
            prev["token_count"] = estimate_token_count(prev["text"])
            idx += 1
            continue

        if idx + 1 < len(chunks):
            nxt = chunks[idx + 1]
            nxt["text"] = f"{chunk['text']}\n{nxt['text']}".strip()
            nxt["token_count"] = estimate_token_count(nxt["text"])
            idx += 1
            continue

        merged.append(chunk)
        idx += 1

    return merged


def _build_chunk(
    *,
    base_chunk_id: str,
    metadata: dict[str, str],
    article_id: str,
    article_title: str,
    chapter: str,
    text: str,
) -> dict[str, Any]:
    safe_text = text.strip()
    chunk = {
        "chunk_id": base_chunk_id,
        "regulation": metadata.get("regulation", ""),
        "jurisdiction": metadata.get("jurisdiction", ""),
        "language": metadata.get("language", ""),
        "article_id": article_id,
        "article_title": article_title,
        "chapter": chapter or "",
        "text": safe_text,
        "token_count": estimate_token_count(safe_text),
    }
    for key, value in chunk.items():
        if value is None:
            chunk[key] = ""
    return chunk


def _regulation_prefix(file_name: str) -> str:
    name = file_name.lower()
    if name.endswith("_full.md"):
        name = name[:-8]
    return _slugify(name)


def _normalize_article_id_for_subchunks(article_id: str, article_no: int | None) -> str:
    if article_no is not None:
        return f"Article_{article_no}"
    return article_id.replace(" ", "_")


def _extract_article_number(article_id: str) -> int | None:
    eu_match = _EU_ARTICLE_ID_RE.match(article_id)
    if eu_match:
        return int(eu_match.group(1))

    cn_match = _CN_ARTICLE_ID_RE.match(article_id)
    if not cn_match:
        return None
    numeral = cn_match.group(1)
    if numeral.isdigit():
        return int(numeral)
    return _cn_numeral_to_int(numeral)


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
            unit = units[ch]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
    total += current
    return total


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

