"""
omni.core.knowledge - Knowledge Management Subsystem

Modules:
- config: Configuration from references.yaml
- ingestion: File discovery and chunking
- storage: LanceDB operations
- librarian: Librarian main class

Usage:
    from omni.core.knowledge import Librarian, ChunkMode, get_knowledge_config
"""

from .config import KnowledgeConfig, get_knowledge_config, reset_config
from .ingestion import FileIngestor
from .librarian import Librarian, ChunkMode
from .storage import KnowledgeStorage

__all__ = [
    "KnowledgeConfig",
    "get_knowledge_config",
    "reset_config",
    "FileIngestor",
    "KnowledgeStorage",
    "Librarian",
    "ChunkMode",
]
