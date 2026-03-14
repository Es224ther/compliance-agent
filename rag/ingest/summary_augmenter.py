from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from config.llm import get_async_client
from config.settings import get_settings


SYSTEM_PROMPT = """
你是一位专业的数据合规律师助手。
请用 150 字以内（中文）概括以下法规条款的核心要求和适用场景。
要求：直接说明该条款规定了什么义务、针对哪类主体、在什么条件下触发。
不要使用"本条款"开头，直接描述内容。
""".strip()

DEFAULT_SUMMARY_MODEL = "claude-sonnet-4-20250514"
DEFAULT_CACHE_PATH = Path("data/kb/summary_cache.json")


def augment_summaries(
    chunks: list[dict[str, Any]],
    *,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    max_concurrent: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """Sync wrapper for async summary augmentation."""
    return asyncio.run(
        augment_summaries_async(
            chunks,
            cache_path=cache_path,
            max_concurrent=max_concurrent,
            model_name=model_name,
        )
    )


async def augment_summaries_async(
    chunks: list[dict[str, Any]],
    *,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    max_concurrent: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """Generate and attach summary field for each chunk with local cache."""
    safe_concurrency = max(1, min(max_concurrent, 5))
    cache_file = Path(cache_path)
    cache = _load_cache(cache_file)
    resolved_model_name = _resolve_model_name(model_name)

    pending = [chunk for chunk in chunks if chunk.get("chunk_id") and chunk["chunk_id"] not in cache]
    if pending:
        client = get_async_client()
        semaphore = asyncio.Semaphore(safe_concurrency)

        async def worker(chunk: dict[str, Any]) -> None:
            chunk_id = str(chunk.get("chunk_id", "")).strip()
            if not chunk_id:
                return
            async with semaphore:
                summary = await _generate_summary(client, chunk, model_name=resolved_model_name)
                cache[chunk_id] = summary
                _save_cache(cache_file, cache)

        await asyncio.gather(*(worker(chunk) for chunk in pending))

    enriched: list[dict[str, Any]] = []
    for chunk in chunks:
        copied = dict(chunk)
        chunk_id = str(copied.get("chunk_id", "")).strip()
        copied["summary"] = cache.get(chunk_id, "")
        enriched.append(copied)
    return enriched


async def _generate_summary(
    client: Any,
    chunk: dict[str, Any],
    *,
    model_name: str,
) -> str:
    payload = _build_user_payload(chunk)
    response = await client.messages.create(
        model=model_name,
        system=SYSTEM_PROMPT,
        max_tokens=220,
        temperature=0.1,
        messages=[{"role": "user", "content": payload}],
    )
    return _read_text_response(response).strip()


def _build_user_payload(chunk: dict[str, Any]) -> str:
    regulation = chunk.get("regulation", "")
    jurisdiction = chunk.get("jurisdiction", "")
    article_id = chunk.get("article_id", "")
    article_title = chunk.get("article_title", "")
    chapter = chunk.get("chapter", "")
    text = chunk.get("text", "")
    return (
        f"法规: {regulation}\n"
        f"法域: {jurisdiction}\n"
        f"章节: {chapter}\n"
        f"条款编号: {article_id}\n"
        f"条款标题: {article_title}\n"
        f"条款内容:\n{text}"
    )


def _read_text_response(response: Any) -> str:
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            return text
    return ""


def _load_cache(cache_file: Path) -> dict[str, str]:
    if not cache_file.exists():
        return {}
    try:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
    except json.JSONDecodeError:
        pass
    return {}


def _save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _resolve_model_name(model_name: str | None) -> str:
    if model_name and model_name.strip():
        return model_name.strip()
    configured = get_settings().model_name
    if configured and configured.strip():
        return configured.strip()
    return DEFAULT_SUMMARY_MODEL

