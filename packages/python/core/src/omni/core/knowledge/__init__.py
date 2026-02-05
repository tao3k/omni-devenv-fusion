"""
omni.core.knowledge - Knowledge Management Subsystem

Modules:
- config: Configuration from references.yaml
- types: Knowledge entry type definitions (from Rust omni-knowledge)
- librarian: Librarian main class

Usage:
    from omni.core.knowledge import Librarian, ChunkMode, get_knowledge_config
    from omni.core.knowledge.types import KnowledgeEntry, KnowledgeCategory

Note:
    This module uses Rust bindings from omni-knowledge crate for
    high-performance knowledge management.
"""

from .config import KnowledgeConfig, get_knowledge_config, reset_config
from .librarian import Librarian, ChunkMode

# Re-export types from Rust bindings
try:
    from omni_knowledge import (
        KnowledgeCategory,
        KnowledgeEntry,
        KnowledgeSearchQuery,
        KnowledgeStats,
    )

    _HAS_RUST_BINDINGS = True
except ImportError:
    _HAS_RUST_BINDINGS = False
    # Fallback placeholder types if Rust bindings not available
    KnowledgeCategory = None
    KnowledgeEntry = None
    KnowledgeSearchQuery = None
    KnowledgeStats = None

__all__ = [
    "KnowledgeConfig",
    "get_knowledge_config",
    "reset_config",
    "Librarian",
    "ChunkMode",
    "KnowledgeCategory",
    "KnowledgeEntry",
    "KnowledgeSearchQuery",
    "KnowledgeStats",
    "_HAS_RUST_BINDINGS",
]
