"""
Fake VectorStore for Testing.

A lightweight in-memory implementation of VectorStoreProtocol for fast testing.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


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
    ) -> List[Dict[str, Any]]: ...

    async def delete_collection(self, collection: str) -> None: ...

    async def get_collection(self, collection: str) -> Optional[Dict[str, Any]]: ...


class FakeVectorStore:
    """
    In-memory fake vector store for testing.

    Implements VectorStoreProtocol for seamless replacement in tests.

    Usage:
        store = FakeVectorStore()
        await store.add_documents("test", ["doc1", "doc2"], ["id1", "id2"])
        results = await store.search("test", "query")
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
    ) -> List[Dict[str, Any]]:
        """Search for documents in a collection using simple keyword matching."""
        if collection not in self._collections:
            return []

        data = self._collections[collection]
        results = []

        for doc, doc_id, meta in zip(
            data["documents"],
            data["ids"],
            data["metadata"],
        ):
            # Simple keyword matching for testing
            query_lower = query.lower()
            if query_lower in doc.lower():
                results.append(
                    {
                        "id": doc_id,
                        "content": doc,
                        "metadata": meta,
                        "score": 1.0,
                    }
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
