# schema/memory.py
# RAG Neural Memory (Phase 11 New)

from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A single memory entry in the neural matrix."""

    key: str = Field(..., description="Memory key/identifier")
    value: str = Field(..., description="Memory content")
    category: str = Field(..., description="Memory category")
    embedding: Optional[List[float]] = Field(
        None, description="Vector embedding (for RAG retrieval)"
    )
    source: str = Field(..., description="Where this memory came from")
    timestamp: str = Field(..., description="When this was recorded")
    access_count: int = Field(default=0, description="Times this memory has been accessed")


class RecallQuery(BaseModel):
    """Query to neural memory system."""

    query: str = Field(..., description="Natural language query")
    category: Optional[str] = Field(None, description="Filter by category")
    limit: int = Field(default=5, ge=1, le=20, description="Max results to return")


class RecallResult(BaseModel):
    """Result from neural memory recall."""

    query: str = Field(..., description="Original query")
    memories: List[MemoryEntry] = Field(default_factory=list, description="Retrieved memories")
    relevance_scores: List[float] = Field(
        default_factory=list, description="Relevance scores for each memory"
    )
    source: str = Field(default="neural_matrix", description="System source")


__all__ = ["MemoryEntry", "RecallQuery", "RecallResult"]
