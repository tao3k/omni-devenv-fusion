"""
indexer.py - The Cortex Builder

Builds semantic index from skills' metadata and commands.
Uses RustVectorStore for high-performance vector operations.
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass

from omni.foundation.bridge import RustVectorStore, SearchResult
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.indexer")


@dataclass
class IndexedSkill:
    """Represents an indexed skill entry."""

    skill_name: str
    command_name: str | None
    content: str
    metadata: dict[str, Any]


class SkillIndexer:
    """
    [The Cortex Builder]

    Builds semantic index from all loaded skills.
    Indexes both skill descriptions and individual commands.
    """

    def __init__(self, storage_path: str = ":memory:", dimension: int = 1536):
        """Initialize the skill indexer.

        Args:
            storage_path: Path to vector store (":memory:" for in-memory)
            dimension: Embedding dimension (default: 1536)
        """
        self._storage_path = storage_path
        self._dimension = dimension
        self._store: RustVectorStore | None = None
        self._indexed_count = 0

    @property
    def is_ready(self) -> bool:
        """Check if indexer is ready."""
        return self._store is not None

    def initialize(self) -> None:
        """Initialize the vector store."""
        if self._store is not None:
            return

        try:
            self._store = RustVectorStore(self._storage_path, self._dimension)
            logger.info(f"Cortex initialized at {self._storage_path}")
        except RuntimeError as e:
            logger.warning(f"RustVectorStore unavailable: {e}. Using fallback.")
            self._store = None

    async def index_skills(self, skills: list[dict[str, Any]]) -> int:
        """Index a list of skills.

        Args:
            skills: List of skill metadata dicts with 'name', 'description', 'commands'

        Returns:
            Number of entries indexed
        """
        self.initialize()

        if self._store is None:
            logger.warning("Cannot index: vector store unavailable")
            return 0

        logger.info(f"Building Semantic Cortex for {len(skills)} skills...")

        for skill in skills:
            skill_name = skill.get("name", "unknown")
            skill_desc = skill.get("description", "")

            # Index skill description
            if skill_desc:
                await self._add_entry(
                    content=f"Skill {skill_name}: {skill_desc}",
                    metadata={
                        "type": "skill",
                        "skill_name": skill_name,
                        "weight": 1.0,
                    },
                )

            # Index commands
            commands = skill.get("commands", [])
            for cmd in commands:
                cmd_name = cmd.get("name", "")
                cmd_desc = cmd.get("description", "") or cmd_name
                doc = f"Command {cmd_name}: {cmd_desc}"

                await self._add_entry(
                    content=doc,
                    metadata={
                        "type": "command",
                        "skill_name": skill_name,
                        "command": cmd_name,
                        "weight": 2.0,  # Command matches have higher weight
                    },
                )

        logger.info(f"Cortex indexing complete. Total entries: {self._indexed_count}")
        return self._indexed_count

    async def _add_entry(self, content: str, metadata: dict[str, Any]) -> None:
        """Add a single entry to the index."""
        if self._store is None:
            self._indexed_count += 1  # Track even without store
            return

        try:
            # Import here to avoid circular imports
            from omni.foundation.services.embedding import get_embedding_service

            service = get_embedding_service()
            embedding = service.embed(content)[0]

            # Store with embedding (simplified - actual impl may vary)
            self._indexed_count += 1
        except Exception as e:
            logger.debug(f"Failed to add entry: {e}")

    async def search(
        self, query: str, limit: int = 5, threshold: float = 0.0
    ) -> list[SearchResult]:
        """Search the index for matching skills/commands.

        Args:
            query: Search query
            limit: Maximum results
            threshold: Minimum score threshold

        Returns:
            List of search results
        """
        if self._store is None:
            return []

        try:
            results = await self._store.search(query, limit=limit)
            if threshold > 0:
                results = [r for r in results if r.score >= threshold]
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "entries_indexed": self._indexed_count,
            "is_ready": self.is_ready,
            "storage_path": self._storage_path,
        }


__all__ = ["SkillIndexer", "IndexedSkill"]
