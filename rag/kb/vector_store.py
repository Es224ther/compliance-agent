from __future__ import annotations

import threading
from pathlib import Path
from typing import Any


DEFAULT_VECTOR_DIR = Path("data/kb/vectors")
EU_COLLECTION = "compliance_eu"
CN_COLLECTION = "compliance_cn"

EU_REGULATIONS = {"GDPR", "EU AI ACT"}
CN_REGULATIONS = {"PIPL", "DSL", "CSL", "AIGC MARKING MEASURES"}


class VectorStore:
    """ChromaDB-backed persistent vector storage."""

    def __init__(self, persist_directory: str | Path = DEFAULT_VECTOR_DIR) -> None:
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = self._create_client(self.persist_directory)
        self._collections: dict[str, Any] = {}
        self._embedder = _EmbeddingProvider()

    def upsert(self, chunks: list[dict[str, Any]]) -> None:
        grouped: dict[str, list[dict[str, Any]]] = {EU_COLLECTION: [], CN_COLLECTION: []}
        for chunk in chunks:
            collection_name = self._collection_for_chunk(chunk)
            grouped[collection_name].append(chunk)

        for collection_name, items in grouped.items():
            if not items:
                continue
            collection = self._get_collection(collection_name)
            ids = [str(item["chunk_id"]) for item in items]
            documents = [str(item.get("search_text") or item.get("text") or "") for item in items]
            embeddings = self._embedder.embed_texts(documents)
            metadatas = [self._to_metadata(item) for item in items]
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

    def query(
        self,
        embedding: list[float],
        n_results: int,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        target_collections = self._collections_for_filter(filter)
        all_hits: list[dict[str, Any]] = []

        for collection_name in target_collections:
            collection = self._get_collection(collection_name)
            result = collection.query(
                query_embeddings=[embedding],
                n_results=max(1, n_results),
                where=filter or None,
                include=["metadatas", "documents", "distances"],
            )
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            for idx, chunk_id in enumerate(ids):
                metadata = metas[idx] if idx < len(metas) else {}
                document = docs[idx] if idx < len(docs) else ""
                distance = distances[idx] if idx < len(distances) else None
                hit = {"chunk_id": chunk_id, "text": document, "distance": distance}
                if isinstance(metadata, dict):
                    hit.update(metadata)
                all_hits.append(hit)

        all_hits.sort(key=lambda item: item.get("distance", 1e9))
        return all_hits[:n_results]

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        for collection_name in (EU_COLLECTION, CN_COLLECTION):
            collection = self._get_collection(collection_name)
            collection.delete(ids=chunk_ids)

    def count(self) -> int:
        total = 0
        for collection_name in (EU_COLLECTION, CN_COLLECTION):
            collection = self._get_collection(collection_name)
            total += int(collection.count())
        return total

    def fetch_all(self, jurisdiction: str = "All") -> list[dict[str, Any]]:
        target_collections: list[str]
        j = jurisdiction.upper()
        if j == "EU":
            target_collections = [EU_COLLECTION]
        elif j == "CN":
            target_collections = [CN_COLLECTION]
        else:
            target_collections = [EU_COLLECTION, CN_COLLECTION]

        output: list[dict[str, Any]] = []
        for collection_name in target_collections:
            collection = self._get_collection(collection_name)
            result = collection.get(include=["metadatas", "documents"])
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            for idx, chunk_id in enumerate(ids):
                item: dict[str, Any] = {"chunk_id": chunk_id, "text": docs[idx] if idx < len(docs) else ""}
                if idx < len(metas) and isinstance(metas[idx], dict):
                    item.update(metas[idx])
                output.append(item)
        return output

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_texts([text])[0]

    @staticmethod
    def _create_client(persist_directory: Path) -> Any:
        try:
            import chromadb
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "chromadb is required for vector storage. Install dependencies before running ingest."
            ) from exc
        return chromadb.PersistentClient(path=str(persist_directory))

    def _get_collection(self, collection_name: str) -> Any:
        if collection_name not in self._collections:
            self._collections[collection_name] = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[collection_name]

    def _collection_for_chunk(self, chunk: dict[str, Any]) -> str:
        jurisdiction = str(chunk.get("jurisdiction", "")).upper()
        if jurisdiction == "EU":
            return EU_COLLECTION
        if jurisdiction == "CN":
            return CN_COLLECTION

        regulation = str(chunk.get("regulation", "")).upper()
        if regulation in EU_REGULATIONS:
            return EU_COLLECTION
        if regulation in CN_REGULATIONS:
            return CN_COLLECTION
        return CN_COLLECTION

    def _collections_for_filter(self, filter: dict[str, Any] | None) -> list[str]:
        if not filter:
            return [EU_COLLECTION, CN_COLLECTION]
        jurisdiction = str(filter.get("jurisdiction", "")).upper()
        if jurisdiction == "EU":
            return [EU_COLLECTION]
        if jurisdiction == "CN":
            return [CN_COLLECTION]
        return [EU_COLLECTION, CN_COLLECTION]

    @staticmethod
    def _to_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
        tags = chunk.get("tags", [])
        if isinstance(tags, list):
            tags_value = ",".join(str(tag) for tag in tags)
        else:
            tags_value = str(tags)

        metadata = {
            "regulation": str(chunk.get("regulation", "")),
            "jurisdiction": str(chunk.get("jurisdiction", "")),
            "language": str(chunk.get("language", "")),
            "article_id": str(chunk.get("article_id", "")),
            "article_title": str(chunk.get("article_title", "")),
            "chapter": str(chunk.get("chapter", "")),
            "token_count": int(chunk.get("token_count", 0) or 0),
            "summary": str(chunk.get("summary", "")),
            "tags": tags_value,
        }
        return metadata


class _EmbeddingProvider:
    """Priority: bge-m3 -> multilingual-e5-large -> OpenAI embedding."""

    def __init__(self) -> None:
        self._provider: Any | None = None
        self._provider_name = ""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        provider = self._get_provider()
        return provider.embed(texts)

    def _get_provider(self) -> Any:
        if self._provider is not None:
            return self._provider

        errors: list[str] = []
        try:
            self._provider = _SentenceTransformerProvider(
                model_candidates=("BAAI/bge-m3", "intfloat/multilingual-e5-large")
            )
            self._provider_name = "sentence-transformers"
            return self._provider
        except Exception as exc:
            errors.append(f"sentence-transformers: {exc}")

        try:
            self._provider = _OpenAIEmbeddingProvider(model="text-embedding-3-small")
            self._provider_name = "openai"
            return self._provider
        except Exception as exc:
            errors.append(f"openai: {exc}")

        raise RuntimeError(
            "No embedding provider available. Tried bge-m3/e5/openai. "
            f"Details: {' | '.join(errors)}"
        )


class _SentenceTransformerProvider:
    def __init__(self, model_candidates: tuple[str, ...]) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError("sentence-transformers is not installed") from exc

        last_error: Exception | None = None
        for candidate in model_candidates:
            try:
                self._model = SentenceTransformer(candidate, device="cpu")
                self._model_name = candidate
                return
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"failed to load models {model_candidates}: {last_error}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, batch_size=16)
        return vectors.tolist()


_default_store: "VectorStore | None" = None
_default_store_lock = threading.Lock()


def get_default_store() -> VectorStore:
    """Return a process-wide singleton VectorStore (thread-safe)."""
    global _default_store
    if _default_store is None:
        with _default_store_lock:
            if _default_store is None:
                _default_store = VectorStore()
    return _default_store


class _OpenAIEmbeddingProvider:
    def __init__(self, model: str) -> None:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("openai is not installed") from exc

        import os

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]
