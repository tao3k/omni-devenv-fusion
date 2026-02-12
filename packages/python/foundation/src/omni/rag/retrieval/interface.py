"""Typed retrieval interfaces and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RetrievalResult:
    """Normalized retrieval result."""

    id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "vector"


@dataclass
class RetrievalConfig:
    """Retrieval query configuration."""

    collection: str = "knowledge"
    top_k: int = 10
    score_threshold: float = 0.0
    where_filter: str | dict[str, Any] | None = None
    batch_size: int | None = None
    fragment_readahead: int | None = None
    batch_readahead: int | None = None
    scan_limit: int | None = None
    keywords: list[str] | None = None

    def to_vector_search_kwargs(self) -> dict[str, Any]:
        """Render scanner/search kwargs aligned with Rust options contract."""
        return {
            "where_filter": self.where_filter,
            "batch_size": self.batch_size,
            "fragment_readahead": self.fragment_readahead,
            "batch_readahead": self.batch_readahead,
            "scan_limit": self.scan_limit,
        }


class RetrievalBackend(Protocol):
    """Abstract retrieval backend."""

    async def search(self, query: str, config: RetrievalConfig) -> list[RetrievalResult]:
        """Run search and return ranked results."""

    async def index(self, documents: list[dict[str, Any]], collection: str) -> int:
        """Index a list of documents, returning stored count."""

    async def get_stats(self, collection: str) -> dict[str, Any]:
        """Return backend stats for a collection."""


__all__ = [
    "RetrievalResult",
    "RetrievalConfig",
    "RetrievalBackend",
]
