"""
Fake VectorStore for Testing.

A lightweight in-memory implementation of VectorStoreProtocol for fast testing.
Supports ChromaDB-style filtering and search results.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Fake search result matching ChromaDB's SearchResult structure."""

    id: str
    content: str
    metadata: Dict[str, Any]
    distance: float = 0.0

    @property
    def score(self) -> float:
        """Convert distance to similarity score."""
        return 1.0 - self.distance


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Protocol for vector store operations."""

    async def add_documents(
        self,
        collection: str,
        documents: List[str],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None: ...

    async def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        where_filter: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]: ...

    async def delete_collection(self, collection: str) -> None: ...

    async def get_collection(self, collection: str) -> Optional[Dict[str, Any]]: ...


class FakeVectorStore:
    """
    In-memory fake vector store for testing.

    Implements VectorStoreProtocol for seamless replacement in tests.
    Supports ChromaDB-style where_filter for filtering by metadata.

    Usage:
        store = FakeVectorStore()
        await store.add_documents("test", ["doc1", "doc2"], ["id1", "id2"])
        results = await store.search("test", "query")

    Filtering:
        await store.search("test", "query", where_filter={"installed": "true"})
    """

    def __init__(self):
        self._collections: Dict[str, Dict[str, Any]] = {}

    async def add_documents(
        self,
        collection: str,
        documents: List[str],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add documents to a collection."""
        if collection not in self._collections:
            self._collections[collection] = {
                "documents": [],
                "ids": [],
                "metadata": [],
            }

        for doc, doc_id, meta in zip(documents, ids, metadata or []):
            self._collections[collection]["documents"].append(doc)
            self._collections[collection]["ids"].append(doc_id)
            self._collections[collection]["metadata"].append(meta or {})

    async def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        where_filter: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]:
        """
        Search for documents in a collection using simple keyword matching.

        Supports ChromaDB-style filtering via where_filter:
            where_filter={"installed": "true"}  # Only installed skills
            where_filter={"type": "remote"}      # Only remote skills
        """
        if collection not in self._collections:
            return []

        data = self._collections[collection]
        results = []
        query_lower = query.lower()

        for doc, doc_id, meta in zip(
            data["documents"],
            data["ids"],
            data["metadata"],
        ):
            # Apply where_filter if provided
            if where_filter:
                match = True
                for key, value in where_filter.items():
                    if meta.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # Simple keyword matching for testing
            if query_lower in doc.lower():
                # Calculate fake distance based on keyword relevance
                distance = 0.0 if query_lower in doc.lower() else 0.5
                results.append(
                    SearchResult(
                        id=doc_id,
                        content=doc,
                        metadata=meta,
                        distance=distance,
                    )
                )
                if len(results) >= n_results:
                    break

        return results

    async def delete_collection(self, collection: str) -> None:
        """Delete a collection."""
        self._collections.pop(collection, None)

    async def get_collection(self, collection: str) -> Optional[Dict[str, Any]]:
        """Get collection data."""
        return self._collections.get(collection)

    async def count(self, collection: str) -> int:
        """Count documents in a collection."""
        if collection not in self._collections:
            return 0
        return len(self._collections[collection]["documents"])

    async def clear(self) -> None:
        """Clear all collections."""
        self._collections.clear()

    def has_collection(self, collection: str) -> bool:
        """Check if a collection exists."""
        return collection in self._collections

    def count_documents(self, collection: str) -> int:
        """Count documents in a collection."""
        if collection not in self._collections:
            return 0
        return len(self._collections[collection]["documents"])
