"""
agent/core/memory/manager.py
Phase 71: The Memory Mesh - Memory Manager

Provides episodic memory storage and retrieval capabilities.

Usage:
    from agent.core.memory.manager import get_memory_manager

    mm = get_memory_manager()

    # Record an experience
    await mm.add_experience(
        user_query="git commit fails",
        tool_calls=["git.commit"],
        outcome="failure",
        error_msg="lock file exists",
        reflection="Delete .git/index.lock to resolve"
    )

    # Recall relevant experiences
    memories = await mm.recall("git commit error")
"""

from __future__ import annotations

import json
import structlog
from typing import Any, List, Optional

from .types import InteractionLog

# Lazy imports to avoid circular deps and slow startup
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class MemoryManager:
    """
    Manages episodic memory storage and retrieval.

    Responsibilities:
    - Write structured interaction logs to vector store
    - Retrieve relevant past experiences via semantic search
    - Provide high-level API for memory operations
    """

    def __init__(self) -> None:
        """Initialize memory manager (lazy vector store connection)."""
        self._store: Any = None
        self._initialized = False

    def _ensure_store(self) -> Any:
        """Lazy initialization of vector store."""
        if self._store is None and not self._initialized:
            try:
                from agent.core.vector_store import get_vector_memory

                self._store = get_vector_memory()
                self._initialized = True
                _get_logger().info("Memory manager initialized")
            except Exception as e:
                _get_logger().warning("Failed to initialize memory store", error=str(e))
        return self._store

    async def add_experience(
        self,
        user_query: str,
        tool_calls: List[str],
        outcome: str,
        reflection: str,
        error_msg: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str | None:
        """
        Record a new experience to memory.

        Args:
            user_query: The user's original query/intent
            tool_calls: List of tools that were called
            outcome: "success" or "failure"
            reflection: Synthesized lesson learned
            error_msg: Error message if outcome was failure
            session_id: Optional session identifier

        Returns:
            The ID of the created record, or None if failed
        """
        store = self._ensure_store()
        if not store:
            _get_logger().warning("Memory store not available, skipping record")
            return None

        try:
            # Create structured log
            log = InteractionLog(
                user_query=user_query,
                session_id=session_id,
                tool_calls=tool_calls,
                outcome=outcome,
                error_msg=error_msg,
                reflection=reflection,
            )

            # Convert to vector store record
            record = log.to_vector_record()

            # Add to vector store
            success = await store.add_memory(record)

            if success:
                _get_logger().info(
                    "Experience recorded",
                    id=log.id,
                    outcome=outcome,
                    query_preview=user_query[:50],
                )
                return log.id
            else:
                _get_logger().warning("Failed to add memory record", id=log.id)
                return None

        except Exception as e:
            _get_logger().error("Failed to record experience", error=str(e))
            return None

    async def recall(
        self,
        query: str,
        limit: int = 3,
        outcome_filter: Optional[str] = None,
    ) -> List[InteractionLog]:
        """
        Retrieve relevant past experiences.

        Args:
            query: Natural language query describing the current situation
            limit: Maximum number of memories to return (default: 3, max: 10)
            outcome_filter: Optional filter for "success" or "failure"

        Returns:
            List of matching InteractionLog objects, sorted by relevance
        """
        store = self._ensure_store()
        if not store:
            _get_logger().warning("Memory store not available, returning empty")
            return []

        try:
            # Search vector store
            results = await store.search_memory(query, limit=limit * 2)  # Get more for filtering

            memories: List[InteractionLog] = []
            seen_ids: set = set()

            for raw in results:
                if len(memories) >= limit:
                    break

                try:
                    # Skip duplicates
                    mem_id = raw.get("id")
                    if mem_id in seen_ids:
                        continue
                    seen_ids.add(mem_id)

                    # Apply outcome filter from raw result
                    raw_outcome = raw.get("outcome", "")
                    if outcome_filter and raw_outcome != outcome_filter:
                        continue

                    # Try to parse metadata
                    metadata = raw.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}
                    elif not isinstance(metadata, dict):
                        metadata = {}

                    # Reconstruct InteractionLog from metadata
                    if metadata.get("user_query"):
                        log = InteractionLog(**metadata)
                        memories.append(log)
                    else:
                        # Fallback: parse from text content
                        # Text format: "Query: ...\nReflection: ..."
                        text = raw.get("content", raw.get("text", ""))
                        timestamp = raw.get("timestamp", "")
                        log = InteractionLog(
                            id=mem_id,
                            timestamp=timestamp,
                            user_query="Retrieved from memory",
                            tool_calls=[],
                            outcome=raw_outcome or "unknown",
                            reflection=text[:500] if text else "No content",
                        )
                        memories.append(log)

                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    _get_logger().warning("Failed to parse memory record", error=str(e))
                    continue

            _get_logger().debug(
                "Memory recall completed",
                query=query[:50],
                found=len(memories),
                filtered=len(results) - len(memories),
            )

            return memories

        except Exception as e:
            _get_logger().error("Failed to recall memories", error=str(e))
            return []

    async def get_recent(self, limit: int = 5) -> List[InteractionLog]:
        """
        Get the most recent memories regardless of content.

        Args:
            limit: Number of recent memories to return

        Returns:
            List of recent InteractionLog objects
        """
        store = self._ensure_store()
        if not store:
            return []

        try:
            # For now, use a generic search that returns recent items
            # In a real implementation, we'd have a time-based query
            results = await store.search_memory("", limit=limit)

            memories: List[InteractionLog] = []
            for raw in results:
                try:
                    metadata = raw.get("metadata", {})
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif not isinstance(metadata, dict):
                        continue

                    memories.append(InteractionLog(**metadata))
                except Exception:
                    continue

            return memories[:limit]

        except Exception as e:
            _get_logger().error("Failed to get recent memories", error=str(e))
            return []

    async def count(self) -> int:
        """Get total number of memories stored."""
        store = self._ensure_store()
        if not store:
            return 0

        try:
            from agent.core.types import VectorTable

            return await store.count(VectorTable.MEMORY.value)
        except Exception:
            return 0


# Singleton instance
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get the singleton MemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


__all__ = [
    "MemoryManager",
    "get_memory_manager",
    "InteractionLog",
]
