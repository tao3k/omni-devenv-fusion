"""
types.py - Python-side Data Structures for Bridge Layer

Defines Pydantic models that wrap Rust types, ensuring type safety
and preventing PyObject leaks into the business layer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


class SearchResult(BaseModel):
    """Represents a single search result from vector store."""

    score: float
    payload: dict[str, Any]
    id: str

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Validate score is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {v}")
        return v


class FileContent(BaseModel):
    """Represents file content with metadata for ingestion."""

    path: str
    content: str
    metadata: dict[str, Any] | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path is not empty."""
        if not v:
            raise ValueError("File path cannot be empty")
        return v


class VectorMetadata(BaseModel):
    """Metadata for vector operations."""

    dimension: int
    distance_metric: str = "cosine"
    index_path: str | None = None


class CodeSymbol(BaseModel):
    """Represents a code symbol (function, class, variable) found by AST."""

    name: str
    symbol_type: str  # "function", "class", "method", "variable"
    file_path: str
    line_number: int
    end_line_number: int | None = None
    docstring: str | None = None
    metadata: dict[str, Any] = {}


class ScanResult(BaseModel):
    """Result of a file or skill scan operation."""

    success: bool
    file_path: str
    symbols: list[CodeSymbol] = []
    references: list[str] = []
    metadata: dict[str, Any] = {}
    error: str | None = None


class SkillStructure(BaseModel):
    """Represents a parsed skill structure."""

    skill_name: str
    skill_path: str
    routing_keywords: list[str] = []
    scripts: list[str] = []
    commands: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}


class IngestResult(BaseModel):
    """Result of ingesting content into vector store."""

    success: bool
    document_id: str | None = None
    chunks_created: int = 0
    error: str | None = None


__all__ = [
    "CodeSymbol",
    "FileContent",
    "IngestResult",
    "ScanResult",
    "SearchResult",
    "SkillStructure",
    "VectorMetadata",
]
