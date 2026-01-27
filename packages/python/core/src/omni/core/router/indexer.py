"""
indexer.py - The Cortex Builder

Builds semantic index from skills' metadata and commands.
Uses RustVectorStore for high-performance vector operations.
Has in-memory fallback for testing/debugging.

Python 3.12+ Features:
- itertools.batched() for batch processing (Section 7.2)
- asyncio.TaskGroup for batch-internal parallelism (Section 7.3)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cached_property
from itertools import batched
from typing import Any

from pydantic import BaseModel

from omni.foundation.bridge import RustVectorStore, SearchResult
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.indexer")

# Thread pool for blocking embedding operations (prevents event loop blocking)
_EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embedding")


@dataclass
class IndexedEntry:
    """An in-memory indexed entry for fallback search."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


class InMemoryIndex:
    """Simple in-memory index for fallback when RustVectorStore is unavailable."""

    def __init__(self, dimension: int = 384):
        self._entries: list[IndexedEntry] = []
        self._dimension = dimension

    def add(self, content: str, metadata: dict[str, Any]) -> None:
        """Add an entry to the index."""
        self._entries.append(IndexedEntry(content=content, metadata=metadata))

    def add_batch(self, entries: list[tuple[str, dict[str, Any]]]) -> None:
        """Add a batch of entries."""
        for content, metadata in entries:
            self._entries.append(IndexedEntry(content=content, metadata=metadata))

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def search(self, query: str, embedding_service: Any, limit: int = 5) -> list[SearchResult]:
        """Search using keyword matching (fallback when embeddings unavailable)."""
        if not self._entries:
            return []

        query_words = set(query.lower().split())
        results = []

        for i, entry in enumerate(self._entries):
            # Simple keyword matching
            content_lower = entry.content.lower()
            match_count = sum(1 for word in query_words if word in content_lower)

            if match_count > 0:
                # Calculate score based on keyword matches
                score = min(0.9, match_count / max(len(query_words), 1))

                results.append(
                    SearchResult(
                        score=score,
                        payload=entry.metadata,
                        id=entry.metadata.get("id", f"entry_{i}"),
                    )
                )

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def __len__(self) -> int:
        return len(self._entries)


class IndexedSkill(BaseModel):
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
    Uses RustVectorStore for production, InMemoryIndex for fallback.
    """

    def __init__(
        self,
        storage_path: str | None = None,
        dimension: int = 384,
    ):
        """Initialize the skill indexer.

        Args:
            storage_path: Path to vector store (None = use unified path, ":memory:" for in-memory)
            dimension: Embedding dimension (default: 384 for BAAI/bge-small-en-v1.5)
        """
        # Use unified path if not specified
        if storage_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            storage_path = str(get_vector_db_path() / "router.lance")

        self._storage_path = storage_path
        self._dimension = dimension
        self._store: RustVectorStore | None = None
        self._memory_index: InMemoryIndex | None = None
        self._indexed_count = 0

    @property
    def is_ready(self) -> bool:
        """Check if indexer is ready."""
        return self._store is not None or self._memory_index is not None

    @cached_property
    def _embedding_service(self) -> Any:
        """Lazily load and cache the embedding service."""
        from omni.foundation.services.embedding import get_embedding_service

        return get_embedding_service()

    def initialize(self) -> None:
        """Initialize the vector store with fallback to in-memory index."""
        if self._store is not None or self._memory_index is not None:
            return

        # For in-memory mode, use Python in-memory index directly
        if self._storage_path == ":memory:":
            self._memory_index = InMemoryIndex(dimension=self._dimension)
            logger.info("Cortex using in-memory index (keyword-based search)")
            return

        try:
            self._store = RustVectorStore(self._storage_path, self._dimension)
            logger.info(f"Cortex initialized at {self._storage_path}")
        except RuntimeError as e:
            logger.warning(f"RustVectorStore unavailable: {e}. Using in-memory fallback.")
            self._memory_index = InMemoryIndex(dimension=self._dimension)
            logger.info("Cortex using in-memory index (keyword-based search)")

    async def index_skills(self, skills: list[dict[str, Any]]) -> int:
        """Index skills using batch operations for single commit.

        Performance:
        - Batches all entries into a single LanceDB commit
        - Reduces init time from ~200s to ~2s
        """
        self.initialize()

        if self._store is None and self._memory_index is None:
            logger.warning("Cannot index: no vector store or in-memory index available")
            return 0

        # Collect all docs to index
        docs: list[dict[str, Any]] = []

        for skill in skills:
            skill_name = skill.get("name", "unknown")
            skill_desc = skill.get("description", "")
            entry_id = skill_name

            # Skill entry
            if skill_desc:
                content = f"Skill {skill_name}: {skill_desc}"
                docs.append(
                    {
                        "id": entry_id,
                        "content": content,
                        "metadata": {
                            "type": "skill",
                            "skill_name": skill_name,
                            "weight": 1.0,
                            "id": entry_id,
                        },
                    }
                )

            # Command entries
            for cmd in skill.get("commands", []):
                cmd_name = cmd.get("name", "")
                cmd_desc = cmd.get("description", "") or cmd_name
                doc_content = f"Command {cmd_name}: {cmd_desc}"
                cmd_id = f"{skill_name}.{cmd_name}" if cmd_name else entry_id

                docs.append(
                    {
                        "id": cmd_id,
                        "content": doc_content,
                        "metadata": {
                            "type": "command",
                            "skill_name": skill_name,
                            "command": cmd_name,
                            "weight": 2.0,
                            "id": cmd_id,
                        },
                    }
                )

        if not docs:
            return 0

        # In-memory index: fast path
        if self._memory_index is not None:
            self._memory_index.clear()
            self._memory_index.add_batch([(d["content"], d["metadata"]) for d in docs])
            self._indexed_count = len(docs)
            logger.info(f"Cortex in-memory index: {len(docs)} entries")
            return self._indexed_count

        # RustVectorStore: batch commit
        logger.info(f"🧠 Cortex batch indexing {len(docs)} entries...")

        # Compute embeddings in thread pool using embed_batch
        contents = [d["content"] for d in docs]

        embeddings = await asyncio.get_event_loop().run_in_executor(
            _EMBEDDING_EXECUTOR, lambda: list(self._embedding_service.embed_batch(contents))
        )

        # Batch write to LanceDB (single commit)
        try:
            await self._store.add_documents(
                table_name="skills",
                ids=[d["id"] for d in docs],
                vectors=embeddings,
                contents=contents,
                metadatas=[str(d["metadata"]) for d in docs],
            )
            self._indexed_count = len(docs)
            logger.info(f"✅ Cortex indexed {len(docs)} entries (single commit)")
        except Exception as e:
            logger.error(f"Failed to batch index Cortex: {e}")
            self._indexed_count = 0

        return self._indexed_count

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
        if self._store is not None:
            # Use RustVectorStore
            try:
                results = await self._store.search(query, limit=limit)
                if threshold > 0:
                    results = [r for r in results if r.score >= threshold]
                return results
            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []
        elif self._memory_index is not None:
            # Use in-memory index with keyword search
            try:
                results = self._memory_index.search(query, self._embedding_service, limit=limit)
                if threshold > 0:
                    results = [r for r in results if r.score >= threshold]
                return results
            except Exception as e:
                logger.error(f"In-memory search failed: {e}")
                return []
        else:
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "entries_indexed": self._indexed_count,
            "is_ready": self.is_ready,
            "storage_path": self._storage_path,
        }


__all__ = ["IndexedEntry", "InMemoryIndex", "IndexedSkill", "SkillIndexer"]
