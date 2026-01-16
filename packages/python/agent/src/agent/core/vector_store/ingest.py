# agent/core/vector_store/ingest.py
"""
Document ingestion for vector store.

Provides add, delete, and batch operations for documents.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .connection import VectorMemory, _get_logger
from .embed import batch_embed


async def add(
    self: VectorMemory,
    documents: list[str],
    ids: list[str],
    collection: str | None = None,
    metadatas: list[Dict[str, Any]] | None = None,
) -> bool:
    """
    Add documents to the vector store.

    Uses batch embedding for parallel processing.

    Args:
        self: VectorMemory instance
        documents: List of document texts to add
        ids: Unique identifiers for each document
        collection: Optional table name
        metadatas: Optional metadata for each document

    Returns:
        True if successful
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for add")
        return False

    table_name = self._get_table_name(collection)

    try:
        # Use batch embedding for parallel processing
        # For small batches (< 10), sequential is faster due to thread overhead
        # For larger batches, parallel processing provides significant speedup
        if len(documents) >= 10:
            _get_logger().debug(f"Using batch embedding for {len(documents)} documents")
            vectors = batch_embed(documents)
        else:
            # Sequential embedding for small batches (avoids thread overhead)
            vectors = [batch_embed([doc])[0] for doc in documents]

        # Convert metadatas to JSON strings
        metadata_strs = [json.dumps(m) if m else "{}" for m in (metadatas or [{}] * len(documents))]

        store.add_documents(
            table_name,
            list(ids),
            vectors,
            list(documents),
            metadata_strs,
        )

        _get_logger().info(
            "Documents added to vector store",
            count=len(documents),
            table=table_name,
        )
        return True

    except Exception as e:
        _get_logger().error("Failed to add documents", error=str(e))
        return False


async def delete(self: VectorMemory, ids: list[str], collection: str | None = None) -> bool:
    """Delete documents by IDs.

    Args:
        self: VectorMemory instance
        ids: List of document IDs to delete
        collection: Optional table name

    Returns:
        True if successful
    """
    store = self._ensure_store()
    if not store:
        return False

    table_name = self._get_table_name(collection)

    try:
        store.delete(table_name, list(ids))
        return True
    except Exception as e:
        _get_logger().error("Failed to delete documents", error=str(e))
        return False


async def count(self: VectorMemory, collection: str | None = None) -> int:
    """Get the number of documents in a collection.

    Args:
        self: VectorMemory instance
        collection: Optional table name

    Returns:
        Number of documents
    """
    store = self._ensure_store()
    if not store:
        return 0

    table_name = self._get_table_name(collection)

    try:
        return store.count(table_name)
    except Exception as e:
        _get_logger().error("Failed to count documents", error=str(e))
        return 0


async def list_collections(self: VectorMemory) -> list[str]:
    """List all table names.

    Args:
        self: VectorMemory instance

    Returns:
        List of collection names
    """
    store = self._ensure_store()
    if not store:
        return []

    # omni-vector doesn't have list_collections, return default
    return [self._default_table]


async def drop_table(self: VectorMemory, collection: str | None = None) -> bool:
    """
    Drop (delete) a collection/table completely.

    This is used for clearing the skill registry during reindex.

    Args:
        self: VectorMemory instance
        collection: Optional table name (defaults to project_knowledge)

    Returns:
        True if successful
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for drop_table")
        return False

    table_name = self._get_table_name(collection)

    try:
        store.drop_table(table_name)
        _get_logger().info("Vector table dropped", table=table_name)
        return True
    except Exception as e:
        _get_logger().error("Failed to drop table", error=str(e))
        return False


# Convenience function for module-level import
async def ingest_knowledge(
    documents: list[str],
    ids: list[str],
    collection: str | None = None,
    metadatas: list[Dict[str, Any]] | None = None,
) -> bool:
    """Ingest documents into knowledge base."""
    return await add(VectorMemory(), documents, ids, collection, metadatas)
