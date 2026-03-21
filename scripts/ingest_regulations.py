from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.ingest.chunker import chunk_regulation
from app.rag.ingest.cross_ref import enrich_chunks_with_cross_refs
from app.rag.ingest.metadata import enrich_chunks_with_tags
from app.rag.ingest.summary_augmenter import augment_summaries
from app.rag.kb.vector_store import VectorStore


REGULATION_FILES = {
    "gdpr": Path("data/regulations/eu/gdpr_full.md"),
    "eu_ai_act": Path("data/regulations/eu/eu_ai_act_full.md"),
    "pipl": Path("data/regulations/cn/pipl_full.md"),
    "dsl": Path("data/regulations/cn/dsl_full.md"),
    "csl": Path("data/regulations/cn/csl_full.md"),
    "aigc_marking": Path("data/regulations/cn/aigc_marking_full.md"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Regulation ingestion pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only process chunks and print stats, do not write vector DB.",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip summary generation to reduce cost/time.",
    )
    parser.add_argument(
        "--regulation",
        type=str,
        help="Process only one regulation key: "
        + ", ".join(sorted(REGULATION_FILES.keys())),
    )
    return parser


def _selected_files(regulation: str | None) -> list[tuple[str, Path]]:
    if not regulation:
        return list(REGULATION_FILES.items())

    key = regulation.strip().lower().replace("-", "_")
    if key not in REGULATION_FILES:
        keys = ", ".join(sorted(REGULATION_FILES.keys()))
        raise ValueError(f"Unknown --regulation '{regulation}'. Available: {keys}")
    return [(key, REGULATION_FILES[key])]


def _build_search_text(chunk: dict[str, Any]) -> str:
    tags = chunk.get("tags", [])
    if isinstance(tags, list):
        tags_text = ", ".join(str(tag) for tag in tags)
    else:
        tags_text = str(tags)

    # Include merged article IDs so short articles remain searchable.
    merged_ids = chunk.get("merged_article_ids", [])
    merged_text = ", ".join(str(mid) for mid in merged_ids) if merged_ids else ""

    parts = [
        str(chunk.get("regulation", "")),
        str(chunk.get("article_id", "")),
        merged_text,
        str(chunk.get("article_title", "")),
        str(chunk.get("chapter", "")),
        tags_text,
        str(chunk.get("summary", "")),
        str(chunk.get("text", "")),
    ]
    return "\n".join(part for part in parts if part).strip()


def run_ingest(*, dry_run: bool, skip_summary: bool, regulation: str | None) -> int:
    selected = _selected_files(regulation)
    raw_chunks_by_key: dict[str, list[dict[str, Any]]] = {}

    for key, path in selected:
        if not path.exists():
            raise FileNotFoundError(f"Regulation file missing: {path}")

        chunks = chunk_regulation(path)
        chunks = enrich_chunks_with_tags(chunks)
        for chunk in chunks:
            chunk.setdefault("summary", "")
        raw_chunks_by_key[key] = chunks

    all_chunks = [chunk for chunks in raw_chunks_by_key.values() for chunk in chunks]

    do_summary = not dry_run and not skip_summary
    if do_summary:
        all_chunks = augment_summaries(all_chunks)
    else:
        for chunk in all_chunks:
            chunk["summary"] = str(chunk.get("summary", ""))

    all_chunks = enrich_chunks_with_cross_refs(all_chunks)
    for chunk in all_chunks:
        chunk["search_text"] = _build_search_text(chunk)

    if dry_run:
        print("Dry-run mode: no vector write")
    else:
        store = VectorStore()
        store.upsert(all_chunks)
        print(f"Vector DB count={store.count()}")

    print("Chunk statistics:")
    chunk_map = {chunk["chunk_id"]: chunk for chunk in all_chunks}
    for key, chunks in raw_chunks_by_key.items():
        total = len(chunks)
        enriched_count = sum(1 for chunk in chunks if chunk["chunk_id"] in chunk_map)
        print(f"- {key}: chunks={total}, enriched={enriched_count}")
    print(f"Total chunks: {len(all_chunks)}")
    return len(all_chunks)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_ingest(
        dry_run=bool(args.dry_run),
        skip_summary=bool(args.skip_summary),
        regulation=args.regulation,
    )


if __name__ == "__main__":
    main()
