"""
Vector store search result model.

Public type returned by semantic and hybrid search.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Result from a vector store search operation."""

    content: str
    metadata: dict[str, Any]
    distance: float
    score: float | None = None
    id: str
