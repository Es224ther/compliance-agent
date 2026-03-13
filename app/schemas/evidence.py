"""Evidence schema returned by RAG retrievers."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceChunk(BaseModel):
    """Canonical evidence chunk used by scoring, guards and reports."""

    model_config = ConfigDict(strict=False)

    regulation: str
    article: str = ""
    jurisdiction: str
    text: str
    summary: str | None = None
    rerank_score: float | None = None
    tags: list[str] = Field(default_factory=list)

    # Backward-compatible metadata used by Day1/Day2 RAG code.
    chunk_id: str | None = None
    language: str | None = None
    article_id: str | None = None
    article_title: str | None = None
    chapter: str | None = None
    distance: float | None = None
    bm25_score: float | None = None
    low_confidence: bool = False

    @model_validator(mode="after")
    def _sync_article_fields(self) -> "EvidenceChunk":
        """Support both article and article_id inputs."""

        if not self.article and self.article_id:
            self.article = self.article_id
        if not self.article_id and self.article:
            self.article_id = self.article
        return self
