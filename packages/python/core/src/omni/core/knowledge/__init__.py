"""
omni.core.knowledge - Knowledge Management Subsystem

High-performance knowledge base with vector search.
Migrated from: src/agent/capabilities/knowledge/

Modules:
- librarian: Core knowledge management (ingest, search, index)
"""

from .librarian import (
    HyperSearch,
    KnowledgeEntry,
    Librarian,
    SearchResult,
)

__all__ = [
    "HyperSearch",
    "KnowledgeEntry",
    "Librarian",
    "SearchResult",
]
