from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from rag.kb.vector_store import get_default_store


def keyword_search(
    query: str,
    jurisdiction: Literal["EU", "CN", "All"] = "All",
    n_results: int = 10,
) -> list[dict[str, Any]]:
    top_n = max(1, n_results)
    index = _KeywordIndex.get()
    return index.search(query=query, jurisdiction=jurisdiction, n_results=top_n)


@dataclass(slots=True)
class _Doc:
    chunk_id: str
    jurisdiction: str
    text: str
    payload: dict[str, Any]


class _KeywordIndex:
    _instance: "_KeywordIndex | None" = None

    @classmethod
    def get(cls) -> "_KeywordIndex":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._docs = self._load_docs()
        self._tokenizer = _Tokenizer()
        self._bm25 = _BM25Wrapper(self._docs, self._tokenizer)

    def search(
        self,
        *,
        query: str,
        jurisdiction: Literal["EU", "CN", "All"],
        n_results: int,
    ) -> list[dict[str, Any]]:
        matches = self._bm25.score(query)
        if jurisdiction in {"EU", "CN"}:
            matches = [item for item in matches if item[0].jurisdiction == jurisdiction]
        matches.sort(key=lambda item: item[1], reverse=True)

        output: list[dict[str, Any]] = []
        for doc, score in matches[:n_results]:
            payload = dict(doc.payload)
            payload["bm25_score"] = float(score)
            output.append(payload)
        return output

    @staticmethod
    def _load_docs() -> list[_Doc]:
        store = get_default_store()
        docs = store.fetch_all(jurisdiction="All")
        output: list[_Doc] = []
        for doc in docs:
            output.append(
                _Doc(
                    chunk_id=str(doc.get("chunk_id", "")),
                    jurisdiction=str(doc.get("jurisdiction", "")),
                    text=str(doc.get("text", "")),
                    payload=doc,
                )
            )
        return output


class _Tokenizer:
    _word_re = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")

    def __init__(self) -> None:
        self._jieba = None
        try:
            import jieba  # type: ignore

            self._jieba = jieba
        except ModuleNotFoundError:
            self._jieba = None

    def tokenize(self, text: str) -> list[str]:
        if self._jieba is not None:
            zh_tokens = [tok.strip() for tok in self._jieba.lcut(text) if tok.strip()]
        else:
            zh_tokens = [tok.group(0) for tok in re.finditer(r"[\u4e00-\u9fff]", text)]
        en_tokens = [tok.group(0).lower() for tok in re.finditer(r"[A-Za-z0-9_]+", text)]
        if zh_tokens or en_tokens:
            return zh_tokens + en_tokens
        return [tok.group(0).lower() for tok in self._word_re.finditer(text)]


class _BM25Wrapper:
    def __init__(self, docs: list[_Doc], tokenizer: _Tokenizer) -> None:
        self._docs = docs
        self._tokenizer = tokenizer
        tokenized = [tokenizer.tokenize(doc.text) for doc in docs]

        self._rank_bm25 = None
        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            self._rank_bm25 = BM25Okapi(tokenized)
        except ModuleNotFoundError:
            self._rank_bm25 = None

        self._tokenized = tokenized

    def score(self, query: str) -> list[tuple[_Doc, float]]:
        tokens = self._tokenizer.tokenize(query)
        if not tokens:
            return []
        if self._rank_bm25 is not None:
            scores = self._rank_bm25.get_scores(tokens)
            return [(self._docs[i], float(scores[i])) for i in range(len(self._docs))]

        # Fallback BM25-like scorer (used only when rank_bm25 is unavailable).
        df: dict[str, int] = {}
        for doc_tokens in self._tokenized:
            seen = set(doc_tokens)
            for tok in seen:
                df[tok] = df.get(tok, 0) + 1

        N = max(1, len(self._tokenized))
        avgdl = sum(len(doc) for doc in self._tokenized) / N
        k1 = 1.5
        b = 0.75

        scored: list[tuple[_Doc, float]] = []
        for idx, doc_tokens in enumerate(self._tokenized):
            dl = max(1, len(doc_tokens))
            tf: dict[str, int] = {}
            for tok in doc_tokens:
                tf[tok] = tf.get(tok, 0) + 1
            score = 0.0
            for q in tokens:
                if q not in tf:
                    continue
                idf = math.log((N - df.get(q, 0) + 0.5) / (df.get(q, 0) + 0.5) + 1.0)
                denom = tf[q] + k1 * (1 - b + b * dl / avgdl)
                score += idf * ((tf[q] * (k1 + 1)) / denom)
            scored.append((self._docs[idx], score))
        return scored

