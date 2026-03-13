"""Evidence schema returned by RAG retrievers."""

from pydantic import BaseModel, ConfigDict, Field


class EvidenceChunk(BaseModel):
    model_config = ConfigDict(strict=False)

    chunk_id: str
    regulation: str
    jurisdiction: str
    language: str | None = None
    article_id: str
    article_title: str | None = None
    chapter: str | None = None
    text: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    distance: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None
    low_confidence: bool = False

