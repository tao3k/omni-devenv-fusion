"""Knowledge Types - Type definitions from Rust omni-knowledge bindings.

This module provides Python type aliases for the Rust omni-knowledge crate,
with fallback enums when Rust bindings are not available.

Usage:
    from omni.core.knowledge.knowledge_types import KnowledgeEntry, KnowledgeCategory

    entry = KnowledgeEntry(
        title="Error Handling Pattern",
        content="Best practices...",
        category=KnowledgeCategory.NOTE,
        tags=["error", "pattern"],
    )
"""

from __future__ import annotations

from enum import Enum


# Fallback enum when Rust bindings are not available
class _FallbackKnowledgeCategory(str, Enum):
    """Fallback KnowledgeCategory when Rust bindings are not available."""

    PATTERN = "patterns"
    SOLUTION = "solutions"
    ERROR = "errors"
    TECHNIQUE = "techniques"
    NOTE = "notes"
    REFERENCE = "references"
    ARCHITECTURE = "architecture"
    WORKFLOW = "workflows"


# Try to import from Rust bindings, fallback to fallback enum for type hints
try:
    from omni_knowledge import (
        KnowledgeCategory as _KnowledgeCategory,
        KnowledgeEntry as _KnowledgeEntry,
        KnowledgeSearchQuery as _KnowledgeSearchQuery,
        KnowledgeStats as _KnowledgeStats,
    )

    # Re-export with simpler names
    KnowledgeCategory = _KnowledgeCategory
    KnowledgeEntry = _KnowledgeEntry
    KnowledgeSearchQuery = _KnowledgeSearchQuery
    KnowledgeStats = _KnowledgeStats

    _HAS_RUST_BINDINGS: bool = True

except ImportError:
    # Use fallback enum when Rust bindings are not available
    KnowledgeCategory = _FallbackKnowledgeCategory  # type: ignore
    KnowledgeEntry = None  # type: ignore
    KnowledgeSearchQuery = None  # type: ignore
    KnowledgeStats = None  # type: ignore

    _HAS_RUST_BINDINGS: bool = False


__all__ = [
    "KnowledgeCategory",
    "KnowledgeEntry",
    "KnowledgeSearchQuery",
    "KnowledgeStats",
    "_HAS_RUST_BINDINGS",
]
