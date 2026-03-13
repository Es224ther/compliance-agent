"""Tool wrapper for hybrid RAG retrieval."""

from __future__ import annotations

from app.schemas import ParsedFields
from app.schemas.evidence import EvidenceChunk
from rag.retriever.hybrid import hybrid_search


def rag_retriever(query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
    """Standard tool entrypoint used by risk agent."""
    return hybrid_search(query=query, parsed_fields=parsed_fields, top_k=5)

