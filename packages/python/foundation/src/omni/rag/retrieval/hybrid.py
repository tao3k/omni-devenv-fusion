"""Hybrid retrieval backend delegating fusion/scoring to Rust."""

from __future__ import annotations

from .errors import HybridRetrievalUnavailableError
from .interface import RetrievalBackend, RetrievalConfig, RetrievalResult
from .normalize import normalize_ranked_results


class HybridRetrievalBackend:
    """Hybrid backend with Rust-owned fusion/scoring."""

    def __init__(self, vector_backend: RetrievalBackend):
        self.vector = vector_backend

    async def search(self, query: str, config: RetrievalConfig) -> list[RetrievalResult]:
        if not hasattr(self.vector, "search_hybrid"):
            raise HybridRetrievalUnavailableError(
                "Hybrid backend requires vector backend with search_hybrid(query, config)."
            )

        native = getattr(self.vector, "search_hybrid")
        fused = await native(query, config)
        return normalize_ranked_results(fused, score_threshold=config.score_threshold)

    async def index(self, documents: list[dict], collection: str) -> int:
        return await self.vector.index(documents, collection)

    async def get_stats(self, collection: str) -> dict:
        vector_stats = await self.vector.get_stats(collection)
        return {
            "backend": "hybrid",
            "collection": collection,
            "engine_owner": "rust",
            "vector": vector_stats,
        }


__all__ = ["HybridRetrievalBackend"]
