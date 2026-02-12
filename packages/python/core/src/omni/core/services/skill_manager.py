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

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable

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

    Callback Support:
    - on_registry_update(callback): Register callback fired when skills change
      The callback is used by MCP Gateway to send notifications/tools/listChanged
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
            vector_store_path: Path for LanceDB storage (default: .cache/omni-vector/skills.lance)
            enable_watcher: Whether to enable Reactive Skill Watcher
            watcher_patterns: File patterns for watcher (default: ["**/*.py"])
            watcher_debounce_seconds: Debounce delay for watcher events
        """
        # Resolve project root
        self.project_root = Path(project_root or Path.cwd()).resolve()

        # LanceDB path - use unified vector DB path from PRJ_CACHE
        from omni.foundation.config.database import get_database_path

        db_path = vector_store_path or get_database_path("skills")

        # Embedding service (singleton pattern)
        self.embedding_service = embedding_service or get_embedding_service()
        # Get dimension from settings (lazy load only when actually embedding)
        from omni.foundation.config.settings import get_setting

        embedding_dimension = get_setting("embedding.dimension", 1024)

        # Initialize Rust Vector Store with dimension from settings
        self.vector_store = PyVectorStore(db_path, embedding_dimension, False)

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
        self._kernel: "Kernel | None" = None  # Kernel reference for Live-Wire integration

        # Callbacks for skill changes (used by MCP Gateway for notifications)
        self._on_update_callbacks: list[Callable[[], None]] = []

        # Debounce state for preventing race conditions with multiple MCP clients
        self._notify_in_progress = False
        self._notify_cooldown_seconds = 1.0  # Cooldown between notifications
        self._last_notify_time: float = 0.0
        self._pending_notify = False  # Flag for coalesced notifications

        # Librarian (initialized in startup to avoid circular imports)
        self.librarian: "Librarian | None" = None

    def on_registry_update(self, callback: Callable[[], None] | Callable[[], Any]) -> None:
        """Register a callback to be fired when skills change.

        This is the key integration point for MCP Gateway.
        When skills are added/modified/removed, the callback is invoked,
        which triggers notifications/tools/listChanged to MCP clients.

        Supports both sync and async callbacks.

        Args:
            callback: Callback function (sync or async, no args)
                     Called when the skill registry changes.

        Example:
            manager = SkillManager()
            manager.on_registry_update(lambda: print("Skills changed!"))
            # Or async:
            manager.on_registry_update(async def on_change(): await notify_clients())
        """
        self._on_update_callbacks.append(callback)
        logger.debug(f"Registered update callback (total: {len(self._on_update_callbacks)})")

    async def _notify_updates(self) -> None:
        """Internal: Notify all registered callbacks of a skill change.

        This is called by the ReactiveSkillWatcher when it processes
        file change events that affect the skill registry.

        Thread-safe with debouncing to prevent race conditions when
        multiple file changes occur in quick succession or when
        multiple MCP clients are connected.
        """
        now = time.monotonic()

        # Check if already processing - mark as pending if so (don't skip)
        if self._notify_in_progress:
            self._pending_notify = True
            logger.debug("🔔 Notification already in progress, marking as pending")
            return

        # Check cooldown - ignore if too soon after last notification
        if now - self._last_notify_time < self._notify_cooldown_seconds:
            logger.debug(
                f"🔔 Notification skipped (cooldown): {now - self._last_notify_time:.2f}s since last"
            )
            return

        self._notify_in_progress = True
        self._pending_notify = False

        try:
            self._last_notify_time = now
            logger.info(
                f"🔔 _notify_updates called with {len(self._on_update_callbacks)} callbacks"
            )

            for i, callback in enumerate(self._on_update_callbacks):
                try:
                    logger.debug(f"🔔 Invoking callback {i + 1}/{len(self._on_update_callbacks)}")
                    # Check if callback is a coroutine function
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    logger.warning(f"Error in update callback {i}: {e}")
        finally:
            self._notify_in_progress = False

        # If a notification came in while we were processing, trigger it now
        if self._pending_notify:
            self._pending_notify = False
            logger.debug("🔔 Processing pending notification")
            # Schedule the next notification (but respect cooldown)
            await asyncio.sleep(0.05)  # Brief delay to batch rapid changes
            await self._notify_updates()

    async def startup(self, initial_scan: bool = False, ingest_knowledge: bool = False):
        """Bootstrap the skill system.

        Args:
            initial_scan: Whether to scan all skill files on startup
            ingest_knowledge: Whether to ingest project knowledge on startup
        """
        from omni.core.runtime.services import ServiceRegistry
        from omni.core.knowledge.librarian import Librarian

        logger.info(
            "Starting SkillManager",
            project_root=str(self.project_root),
            embedding_backend=self.embedding_service.backend,
            enable_watcher=self._enable_watcher,
        )

        # Initialize and register Librarian (for code search capability)
        logger.info("Initializing Librarian service...")
        self.librarian = Librarian(
            project_root=str(self.project_root),
            store=self.vector_store,
            embedder=self.embedding_service,
        )

        # Register services in ServiceRegistry for stateless skill access
        ServiceRegistry.register("skill_manager", self)
        ServiceRegistry.register("librarian", self.librarian)
        ServiceRegistry.register("embedding", self.embedding_service)
        logger.info(f"Registered services: {ServiceRegistry.list_services()}")

        # Optional: Ingest project knowledge
        if ingest_knowledge:
            logger.info("Ingesting project knowledge...")
            result = self.librarian.ingest()
            logger.info(f"Knowledge ingestion complete: {result}")

        # Optional: Initial full scan
        if initial_scan:
            logger.info("Performing initial skill scan...")
            stats = await self.indexer.get_index_stats()
            logger.info(f"Initial scan complete: {stats}")

        # Start Reactive Watcher (Live-Wire)
        if self._enable_watcher:
            self.watcher = ReactiveSkillWatcher(
                indexer=self.indexer,
                patterns=self._watcher_patterns,
                debounce_seconds=self._watcher_debounce,
                kernel=self._kernel,  # Bridge to kernel for Live-Wire reload
            )
            # Bridge watcher events to SkillManager callbacks
            # This enables the full chain: Rust Watcher -> Python Index -> MCP Notification
            # Always set callback (even if empty list) - future callbacks will be added to _on_update_callbacks
            self.watcher.set_on_change_callback(self._notify_updates)
            await self.watcher.start()
            logger.info("⚡ Live-Wire Skill Watcher started")

    async def shutdown(self):
        """Gracefully shutdown the skill system."""
        from omni.core.runtime.services import ServiceRegistry

        logger.info("Shutting down SkillManager...")

        # Unregister services
        ServiceRegistry.unregister("skill_manager")
        ServiceRegistry.unregister("librarian")
        ServiceRegistry.unregister("embedding")

        # Stop watcher first
        if self.watcher:
            await self.watcher.stop()
            self.watcher = None

        self.librarian = None
        logger.info("SkillManager shutdown complete")

    def get_knowledge_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics.

        Returns:
            Dict with knowledge base stats, or empty dict if librarian not initialized
        """
        if self.librarian is None:
            return {"status": "not_initialized"}

        stats = self.librarian.get_stats()
        manifest_status = self.librarian.get_manifest_status()
        return {
            "status": "online",
            **stats,
            "manifest": manifest_status,
        }

    def ingest_knowledge(self, clean: bool = False) -> dict[str, int]:
        """Ingest project knowledge.

        Args:
            clean: If True, drop existing table first

        Returns:
            Ingestion result dict
        """
        if self.librarian is None:
            return {"error": "Librarian not initialized"}

        return self.librarian.ingest(clean=clean)

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

    def set_kernel(self, kernel: "Kernel") -> None:
        """Set the kernel reference for Live-Wire skill reload integration.

        This enables the full automatic refresh chain:
        File change → ReactiveSkillWatcher → kernel.reload_skill() → MCP notification

        Args:
            kernel: The Kernel instance
        """
        self._kernel = kernel
        # If watcher is already running, update it with kernel reference
        if self.watcher is not None:
            self.watcher._kernel = kernel
            logger.debug("Kernel reference set on ReactiveSkillWatcher")
        else:
            logger.debug("Kernel reference stored (watcher not yet created)")

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
