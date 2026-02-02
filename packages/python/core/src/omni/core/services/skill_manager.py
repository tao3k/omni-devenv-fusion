"""
omni.core.services.skill_manager
Service Container for the Skill System.

Bootstraps the Holographic Registry and Reactive Watcher.
Provides a unified interface for:
- Vector Store (LanceDB persistence)
- Skill Indexer (Rust Scan -> Python Embed -> Rust Store)
- Holographic Registry (Virtual tool lookup)
- Reactive Watcher (Live-wire hot reload)

Architecture:
    ┌─────────────────────────────────────────────────────┐
    │                  SkillManager                        │
    ├─────────────────────────────────────────────────────┤
    │  VectorStore (Rust/LanceDB)                         │
    │       ↓                                             │
    │  ┌─────────────┐    ┌─────────────┐                 │
    │  │  Indexer    │───→│  Registry   │                 │
    │  │ (Pipeline)  │    │ (Holographic)│                 │
    │  └─────────────┘    └─────────────┘                 │
    │       ↑                                             │
    │  ┌─────────────┐                                    │
    │  │  Watcher    │ (Rust Events → Python Index)       │
    │  │ (Live-Wire) │                                    │
    │  └─────────────┘                                    │
    └─────────────────────────────────────────────────────┘

Usage:
    manager = SkillManager(project_root="/path/to/project")
    await manager.startup()

    # Tools are now searchable
    tools = await manager.registry.search("file operations")
    print(f"Found {len(tools)} tools")

    await manager.shutdown()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import structlog

from omni_core_rs import PyVectorStore
from omni.foundation.services.embedding import EmbeddingService, get_embedding_service
from omni.core.skills.indexer import SkillIndexer
from omni.core.skills.registry.holographic import HolographicRegistry
from omni.core.kernel.watcher import ReactiveSkillWatcher

logger = structlog.get_logger(__name__)


class SkillManager:
    """
    Central service manager for the skill system.

    This class wires together:
    1. Vector Store - Persistent storage for tool embeddings
    2. Skill Indexer - Processes files into searchable tools
    3. Holographic Registry - Virtual tool lookup interface
    4. Reactive Watcher - Live-wire for hot reload

    All components share the same embedding service for consistency.
    """

    def __init__(
        self,
        project_root: str | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store_path: str | None = None,
        enable_watcher: bool = True,
        watcher_patterns: list[str] | None = None,
        watcher_debounce_seconds: float = 0.5,
    ):
        """Initialize the SkillManager.

        Args:
            project_root: Root directory of the project (auto-detected if None)
            embedding_service: EmbeddingService instance (singleton if None)
            vector_store_path: Path for LanceDB storage (default: .omni/data/lancedb)
            enable_watcher: Whether to enable Reactive Skill Watcher
            watcher_patterns: File patterns for watcher (default: ["**/*.py"])
            watcher_debounce_seconds: Debounce delay for watcher events
        """
        # Resolve project root
        self.project_root = Path(project_root or Path.cwd()).resolve()

        # LanceDB path
        db_path = vector_store_path or str(self.project_root / ".omni" / "data" / "lancedb")

        # Embedding service (singleton pattern)
        self.embedding_service = embedding_service or get_embedding_service()

        # Initialize Rust Vector Store
        self.vector_store = PyVectorStore(db_path, self.embedding_service.dimension, False)

        # Initialize Pipeline Components
        self.indexer = SkillIndexer(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            project_root=str(self.project_root),
        )

        # Initialize Holographic Registry
        self.registry = HolographicRegistry(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
        )

        # Initialize Reactive Watcher (Live-Wire)
        self._enable_watcher = enable_watcher
        self._watcher_patterns = watcher_patterns
        self._watcher_debounce = watcher_debounce_seconds
        self.watcher: ReactiveSkillWatcher | None = None

    async def startup(self, initial_scan: bool = False):
        """Bootstrap the skill system.

        Args:
            initial_scan: Whether to scan all files on startup
                          (disable for large projects, enable for fresh installs)
        """
        logger.info(
            "Starting SkillManager",
            project_root=str(self.project_root),
            embedding_backend=self.embedding_service.backend,
            enable_watcher=self._enable_watcher,
        )

        # Optional: Initial full scan
        if initial_scan:
            logger.info("Performing initial skill scan...")
            stats = await self.indexer.get_index_stats()
            logger.info(f"Initial scan complete: {stats}")

        # Start Reactive Watcher (Live-Wire)
        if self._enable_watcher:
            self.watcher = ReactiveSkillWatcher(
                root_dir=str(self.project_root),
                indexer=self.indexer,
                patterns=self._watcher_patterns,
                debounce_seconds=self._watcher_debounce,
            )
            await self.watcher.start()

        logger.info("SkillManager started successfully")

    async def shutdown(self):
        """Gracefully shutdown the skill system."""
        logger.info("Shutting down SkillManager...")

        # Stop watcher first
        if self.watcher:
            await self.watcher.stop()
            self.watcher = None

        logger.info("SkillManager shutdown complete")

    async def reindex_file(self, file_path: str) -> int:
        """Manually re-index a file.

        Args:
            file_path: Path to the file to re-index

        Returns:
            Number of tools indexed
        """
        return await self.indexer.reindex_file(file_path)

    async def reindex_directory(self, directory: str) -> dict[str, int]:
        """Re-index all files in a directory.

        Args:
            directory: Directory to scan

        Returns:
            Dict mapping file paths to count of indexed tools
        """
        return await self.indexer.index_directory(directory)

    async def search_tools(self, query: str, limit: int = 5) -> list:
        """Search for tools matching the query.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            List of ToolMetadata matching the query
        """
        return await self.registry.search(query, limit=limit)

    async def get_tool(self, name: str):
        """Get a specific tool by name.

        Args:
            name: Tool name to find

        Returns:
            ToolMetadata if found, None otherwise
        """
        return await self.registry.get_tool(name)

    async def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics about the skill system.

        Returns:
            Dict with statistics about the system
        """
        index_stats = await self.indexer.get_index_stats()
        registry_stats = await self.registry.get_stats()

        stats = {
            "project_root": str(self.project_root),
            "embedding_backend": self.embedding_service.backend,
            "embedding_dimension": self.embedding_service.dimension,
            "indexer": index_stats,
            "registry": registry_stats,
            "watcher": None,
        }

        if self.watcher:
            stats["watcher"] = await self.watcher.get_stats()

        return stats

    @property
    def is_running(self) -> bool:
        """Check if the skill system is running."""
        return self.watcher is not None and self.watcher.is_running


# ============================================================================
# Singleton instance for easy access
# ============================================================================

_skill_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """Get or create the global SkillManager instance."""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager


async def startup_skill_manager(
    project_root: str | None = None,
    initial_scan: bool = False,
) -> SkillManager:
    """Convenience function to start the skill system.

    Args:
        project_root: Project root directory
        initial_scan: Whether to scan all files on startup

    Returns:
        The started SkillManager instance
    """
    global _skill_manager
    _skill_manager = SkillManager(project_root=project_root)
    await _skill_manager.startup(initial_scan=initial_scan)
    return _skill_manager


async def shutdown_skill_manager():
    """Shutdown the global skill system."""
    global _skill_manager
    if _skill_manager is not None:
        await _skill_manager.shutdown()
        _skill_manager = None
