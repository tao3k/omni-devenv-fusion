"""
Convenience APIs for the knowledge collection.

Thin wrappers over VectorStoreClient.search and .add with collection="knowledge".
"""

from __future__ import annotations

from typing import Any

from .models import SearchResult
from .store import get_vector_store


async def search_knowledge(query: str, n_results: int = 5) -> list[SearchResult]:
    """Search the knowledge collection (default collection='knowledge')."""
    return await get_vector_store().search(query, n_results, collection="knowledge")


async def add_knowledge(content: str, metadata: dict[str, Any] | None = None) -> bool:
    """Add content to the knowledge collection (default collection='knowledge')."""
    return await get_vector_store().add(content, metadata, collection="knowledge")
