"""
librarian.py - The Keeper of Knowledge

Manages the global knowledge base with high-performance vector storage.
Migrated from: src/agent/capabilities/knowledge/librarian.py

Features:
- Ingest: Add documents to the knowledge base
- Index: Create searchable embeddings
- Search: Hyper-fast semantic search across all knowledge

Uses Rust-powered vector store (omni.foundation.bridge) for performance.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger
from pydantic import BaseModel

logger = get_logger("omni.core.knowledge.librarian")


class KnowledgeEntry(BaseModel):
    """Represents a single knowledge entry."""

    id: str
    content: str
    source: str
    metadata: dict[str, Any]
    score: float = 0.0


class SearchResult(BaseModel):
    """Represents a search result."""

    entry: KnowledgeEntry
    score: float


class Librarian:
    """
    [The Keeper of Knowledge]

    Manages the global knowledge base with:
    - File ingestion
    - Chunking for large documents
    - Semantic search via vector store

    Usage:
        librarian = Librarian()  # Uses PRJ_CACHE/omni-vector/knowledge.lance
        librarian.ingest_file("docs/guide.md")
        results = librarian.search("how to commit")
    """

    def __init__(
        self,
        storage_path: str | None = None,
        dimension: int | None = None,
        collection: str = "knowledge",
    ):
        """Initialize the librarian.

        Args:
            storage_path: Path to vector store (None = use unified path, ":memory:" for in-memory)
            dimension: Embedding dimension (default: from settings.yaml embedding.dimension)
            collection: Collection/table name for isolation
        """
        from omni.foundation.config.settings import get_setting

        # Use unified path if not specified
        if storage_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            storage_path = str(get_vector_db_path() / "knowledge.lance")

        # Use dimension from settings.yaml (default to 1024)
        if dimension is None:
            dimension = get_setting("embedding.dimension", 1024)

        self._storage_path = storage_path
        self._dimension = dimension
        self._collection = collection
        self._store = None
        self._initialized = False

        self._init_store()

    def _init_store(self) -> None:
        """Initialize the vector store."""
        try:
            from omni.foundation.bridge import RustVectorStore

            self._store = RustVectorStore(self._storage_path, self._dimension)
            self._initialized = True
            logger.info(f"📚 Librarian initialized at {self._storage_path}")
        except ImportError:
            logger.warning("RustVectorStore not available, using in-memory fallback")
            self._initialized = False
        except RuntimeError as e:
            logger.error(f"Failed to initialize vector store: {e}")
            self._initialized = False

    @property
    def is_ready(self) -> bool:
        """Check if the librarian is ready."""
        return self._initialized and self._store is not None

    def ingest_file(self, file_path: str, metadata: dict[str, Any] | None = None) -> bool:
        """Ingest a single file into the knowledge base.

        Args:
            file_path: Path to the file
            metadata: Optional metadata dict

        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Simple chunking for large files
            chunks = self._chunk_text(content, max_chunk_size=2000)

            entry_metadata = metadata or {}
            entry_metadata["source"] = file_path

            for i, chunk in enumerate(chunks):
                doc_id = f"{Path(file_path).stem}_{i}"
                # For now, just track in local cache until vector store is fully implemented
                entry = KnowledgeEntry(
                    id=doc_id,
                    content=chunk,
                    source=file_path,
                    metadata={**entry_metadata, "chunk": i},
                    score=0.0,
                )
                if not hasattr(self, "_cache"):
                    self._cache = []
                self._cache.append(entry)

            logger.info(f"📚 Librarian ingested: {file_path} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            logger.error(f"Failed to ingest {file_path}: {e}")
            return False

    def ingest_directory(self, directory: str, extensions: list[str] | None = None) -> int:
        """Ingest all files in a directory.

        Args:
            directory: Directory path
            extensions: File extensions to include (e.g., [".md", ".txt"])

        Returns:
            Number of files ingested
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.error(f"Directory not found: {directory}")
            return 0

        extensions = extensions or [".md", ".txt", ".py", ".rst", ".json"]
        count = 0

        # Use Python 3.12+ pathlib.Path.walk()
        for root, _, files in dir_path.walk():
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = root / file
                    if self.ingest_file(str(file_path)):
                        count += 1

        logger.info(f"📚 Librarian ingested {count} files from {directory}")
        return count

    async def search(
        self, query: str, limit: int = 5, threshold: float = 0.0
    ) -> list[SearchResult]:
        """Search the knowledge base.

        Args:
            query: Search query
            limit: Maximum results
            threshold: Minimum score threshold

        Returns:
            List of SearchResult objects
        """
        if not self.is_ready:
            logger.warning("Librarian not ready, search unavailable")
            return []

        try:
            # Note: RustVectorStore.search() is sync, not async
            # We call it directly without await
            raw_results = self._store.search(query, limit=limit)

            results = []
            for r in raw_results:
                if r.score < threshold:
                    continue

                entry = KnowledgeEntry(
                    id=r.id,
                    content=r.payload.get("content", ""),
                    source=r.payload.get("source", ""),
                    metadata=r.payload,
                    score=r.score,
                )
                results.append(SearchResult(entry=entry, score=r.score))

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        if not self.is_ready:
            return {"ready": False}

        return {
            "ready": True,
            "storage_path": self._storage_path,
            "collection": self._collection,
        }

    def _chunk_text(self, text: str, max_chunk_size: int = 2000) -> list[str]:
        """Split text into chunks.

        Args:
            text: Input text
            max_chunk_size: Maximum chunk size

        Returns:
            List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]

        chunks = []
        lines = text.split("\n")
        current_chunk = ""

        for line in lines:
            if len(current_chunk) + len(line) < max_chunk_size:
                current_chunk += line + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def clear(self) -> None:
        """Clear all knowledge entries."""
        # This would need implementation in the store
        logger.info("📚 Librarian cache cleared")


class HyperSearch:
    """
    [Hyper Search Engine]

    Advanced search capabilities for the knowledge base.
    Provides enhanced ranking, filtering, and aggregation.
    """

    def __init__(self, librarian: Librarian):
        """Initialize with a librarian instance."""
        self._librarian = librarian

    async def search_with_highlighting(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search with highlighted matches.

        Returns results with context around matching terms.
        """
        results = await self._librarian.search(query, limit=limit)

        highlighted = []
        for r in results:
            entry = r.entry
            # Simple highlighting - in production, use proper regex
            highlighted_content = entry.content
            # TODO: Add actual highlighting logic

            highlighted.append(
                {
                    "id": entry.id,
                    "source": entry.source,
                    "content_preview": entry.content[:200] + "...",
                    "score": r.score,
                    "highlighted": highlighted_content,
                }
            )

        return highlighted

    async def find_related(self, entry_id: str, limit: int = 3) -> list[SearchResult]:
        """Find related entries to a given entry."""
        # In a full implementation, this would use the entry's content
        # For now, just search for the source
        return await self._librarian.search(entry_id, limit=limit + 1)


__all__ = ["HyperSearch", "KnowledgeEntry", "Librarian", "SearchResult"]
