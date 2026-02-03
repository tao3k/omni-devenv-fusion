"""LanceDB Storage Operations for Project Librarian."""

from typing import Any

import json


class KnowledgeStorage:
    """Handle LanceDB operations for knowledge chunks."""

    def __init__(
        self,
        store,
        table_name: str = "project_chunks",
    ):
        """Initialize storage.

        Args:
            store: PyVectorStore instance
            table_name: Name of the table to use
        """
        self._store = store
        self._table_name = table_name

    def drop_table(self) -> None:
        """Drop the knowledge table if it exists."""
        try:
            self._store.drop_table(self._table_name)
        except Exception:
            pass

    def add_batch(self, records: list[dict[str, Any]]) -> None:
        """Add a batch of records to the store.

        Args:
            records: List of records with id, text, metadata, vector
        """
        if not records:
            return

        ids = [r["id"] for r in records]
        texts = [r["text"] for r in records]
        metadatas = [r["metadata"] for r in records]
        vectors = [r["vector"] for r in records]

        self._store.add_documents(
            table_name=self._table_name,
            ids=ids,
            contents=texts,
            metadatas=metadatas,
            vectors=vectors,
        )

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search knowledge base.

        Args:
            query_vector: Embedding vector for the query
            limit: Maximum results to return

        Returns:
            List of search results with id, text, score, metadata
        """
        results = self._store.search(
            table_name=self._table_name,
            query=query_vector,
            limit=limit,
        )

        formatted = []
        for res_json in results:
            try:
                res = json.loads(res_json)
                distance = res.get("distance", 1.0)
                score = 1.0 - min(distance, 1.0)

                metadata = res.get("metadata", {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                formatted.append(
                    {
                        "id": res.get("id", ""),
                        "score": score,
                        "text": res.get("content", ""),
                        "metadata": metadata,
                    }
                )
            except (json.JSONDecodeError, TypeError):
                continue

        return formatted

    def count(self) -> int:
        """Get total number of records."""
        try:
            return self._store.count(self._table_name)
        except Exception:
            return 0

    @property
    def table_name(self) -> str:
        """Get the table name."""
        return self._table_name
