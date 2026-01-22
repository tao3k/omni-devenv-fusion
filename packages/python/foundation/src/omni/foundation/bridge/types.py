"""
types.py - Python-side Data Structures for Bridge Layer

Defines dataclasses that wrap Rust types, ensuring type safety
and preventing PyObject leaks into the business layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """Represents a single search result from vector store."""

    score: float
    payload: dict[str, Any]
    id: str

    def __post_init__(self):
        """Validate score is in valid range."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")


@dataclass
class FileContent:
    """Represents file content with metadata for ingestion."""

    path: str
    content: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        """Validate required fields."""
        if not self.path:
            raise ValueError("File path cannot be empty")
        if not isinstance(self.content, str):
            raise ValueError("Content must be a string")


@dataclass
class VectorMetadata:
    """Metadata for vector operations."""

    dimension: int
    distance_metric: str = "cosine"
    index_path: str | None = None


@dataclass
class CodeSymbol:
    """Represents a code symbol (function, class, variable) found by AST."""

    name: str
    symbol_type: str  # "function", "class", "method", "variable"
    file_path: str
    line_number: int
    end_line_number: int | None = None
    docstring: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Result of a file or skill scan operation."""

    success: bool
    file_path: str
    symbols: list[CodeSymbol] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SkillStructure:
    """Represents a parsed skill structure."""

    skill_name: str
    skill_path: str
    routing_keywords: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    """Result of ingesting content into vector store."""

    success: bool
    document_id: str | None = None
    chunks_created: int = 0
    error: str | None = None


__all__ = [
    "SearchResult",
    "FileContent",
    "VectorMetadata",
    "CodeSymbol",
    "ScanResult",
    "SkillStructure",
    "IngestResult",
]
