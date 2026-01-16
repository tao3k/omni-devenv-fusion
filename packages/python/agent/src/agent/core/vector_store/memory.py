# agent/core/vector_store/memory.py
"""
Memory support for vector store.

Provides episodic memory storage and retrieval functionality.
"""

from __future__ import annotations

import json
from typing import Any

from agent.core.types import VectorTable
from .connection import VectorMemory, _get_logger
from .ingest import add


async def add_memory(self: VectorMemory, record: dict[str, Any]) -> bool:
    """
    Add a single memory record to the memory table.

    The Memory Mesh - Episodic Memory Storage.

    Args:
        self: VectorMemory instance
        record: Dict with fields:
            - id: Unique identifier
            - text: Text for embedding
            - metadata: JSON-serializable metadata
            - type: Should be "memory"
            - timestamp: ISO timestamp

    Returns:
        True if successful
    """
    try:
        # Extract fields from record
        record_id = record.get("id", "")
        text = record.get("text", "")
        metadata = record.get("metadata", {})

        # Convert metadata to JSON string if dict
        if isinstance(metadata, dict):
            metadata_str = json.dumps(metadata, ensure_ascii=False)
        else:
            metadata_str = str(metadata)

        # Use existing add method with collection="memory"
        success = await add(
            self,
            documents=[text],
            ids=[record_id],
            collection=VectorTable.MEMORY.value,
            metadatas=[metadata],
        )

        if success:
            _get_logger().debug("Memory added", id=record_id)

        return success

    except Exception as e:
        _get_logger().error("Failed to add memory", error=str(e))
        return False


async def search_memory(self: VectorMemory, query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Search memories using semantic similarity.

    The Memory Mesh - Episodic Memory Retrieval.

    Args:
        self: VectorMemory instance
        query: Natural language query
        limit: Maximum results (default: 5, max: 20)

    Returns:
        List of memory records with id, content, distance, metadata
    """
    from .connection import SearchResult
    from .search import search as vector_search

    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for search_memory")
        return []

    table_name = VectorTable.MEMORY.value
    limit = min(max(1, limit), 20)  # Clamp between 1 and 20

    try:
        # Generate embedding for query
        from .embed import embed_query

        query_vector = embed_query(query)
        if query_vector is None:
            return []

        # Perform search
        raw_results = store.search(table_name, query_vector, limit)

        # Parse results
        results: list[dict[str, Any]] = []
        for r in raw_results:
            try:
                # Handle both dict and raw tuple formats from Rust
                if isinstance(r, dict):
                    record_id = r.get("id", "")
                    content = r.get("content", r.get("text", ""))
                    distance = r.get("distance", 1.0)
                    raw_metadata = r.get("metadata")
                else:
                    # Fallback for tuple format: (id, content, distance, metadata)
                    record_id = r[0] if len(r) > 0 else ""
                    content = r[1] if len(r) > 1 else ""
                    distance = r[2] if len(r) > 2 else 1.0
                    raw_metadata = r[3] if len(r) > 3 else None

                # Parse metadata from JSON string
                metadata = {}
                if raw_metadata:
                    if isinstance(raw_metadata, str):
                        try:
                            metadata = json.loads(raw_metadata)
                        except json.JSONDecodeError:
                            pass
                    elif isinstance(raw_metadata, dict):
                        metadata = raw_metadata

                results.append(
                    {
                        "id": record_id,
                        "content": content,
                        "text": content,
                        "distance": distance,
                        "metadata": metadata,
                        "timestamp": metadata.get("timestamp", ""),
                        "outcome": metadata.get("outcome", ""),
                    }
                )
            except (json.JSONDecodeError, TypeError, IndexError):
                continue

        _get_logger().debug(
            "Memory search completed",
            query=query[:50],
            results=len(results),
        )

        return results

    except Exception as e:
        _get_logger().error("Failed to search memory", error=str(e))
        return []
