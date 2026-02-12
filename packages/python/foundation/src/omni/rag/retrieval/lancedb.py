"""LanceDB-backed retrieval backend."""

from __future__ import annotations

from typing import Any

from omni.foundation.services.vector import get_vector_store

from .interface import RetrievalConfig, RetrievalResult
from .normalize import normalize_ranked_results


class LanceRetrievalBackend:
    """Retrieval backend using foundation VectorStoreClient."""

    def __init__(self, vector_client: Any | None = None):
        self._vector = vector_client or get_vector_store()

    async def search(self, query: str, config: RetrievalConfig) -> list[RetrievalResult]:
        raw_results = await self._vector.search(
            query=query,
            n_results=config.top_k,
            collection=config.collection,
            **config.to_vector_search_kwargs(),
        )
        normalized: list[RetrievalResult] = []
        for item in raw_results:
            score = getattr(item, "score", None)
            if score is None:
                distance = float(getattr(item, "distance", 0.0) or 0.0)
                score = 1.0 / (1.0 + max(distance, 0.0))
            score = float(score)
            if score < config.score_threshold:
                continue
            normalized.append(
                RetrievalResult(
                    id=str(getattr(item, "id", "")),
                    content=str(getattr(item, "content", "")),
                    score=score,
                    metadata=dict(getattr(item, "metadata", {}) or {}),
                    source="vector",
                )
            )
        return normalize_ranked_results(normalized, score_threshold=config.score_threshold)

    async def search_hybrid(self, query: str, config: RetrievalConfig) -> list[RetrievalResult]:
        """Rust-backed hybrid search (vector + BM25 fusion)."""
        raw_results = await self._vector.search_hybrid(
            query=query,
            n_results=config.top_k,
            collection=config.collection,
            keywords=config.keywords,
        )
        normalized: list[RetrievalResult] = []
        for item in raw_results:
            result_id = str(getattr(item, "id", "")).strip()
            content = str(getattr(item, "content", "")).strip()
            metadata = dict(getattr(item, "metadata", {}) or {})
            if not result_id or not content:
                continue
            score = getattr(item, "score", None)
            if score is None:
                distance = float(getattr(item, "distance", 1.0) or 1.0)
                score = max(0.0, 1.0 - distance)
            score = float(score)

            if score < config.score_threshold:
                continue

            normalized.append(
                RetrievalResult(
                    id=result_id,
                    content=content,
                    score=score,
                    metadata=metadata,
                    source=str(metadata.get("source", "hybrid")),
                )
            )
        return normalize_ranked_results(normalized, score_threshold=config.score_threshold)

    async def index(self, documents: list[dict[str, Any]], collection: str) -> int:
        chunks: list[str] = []
        metadata: list[dict[str, Any]] = []
        for doc in documents:
            content = str(doc.get("content", "")).strip()
            if not content:
                continue
            chunks.append(content)
            metadata.append(dict(doc.get("metadata", {}) or {}))
        if not chunks:
            return 0
        return await self._vector.add_batch(chunks=chunks, metadata=metadata, collection=collection)

    async def get_stats(self, collection: str) -> dict[str, Any]:
        count = await self._vector.count(collection=collection)
        cache = self._vector.cache_stats()
        return {
            "backend": "lance",
            "collection": collection,
            "count": count,
            "cache": cache,
        }


__all__ = ["LanceRetrievalBackend"]
