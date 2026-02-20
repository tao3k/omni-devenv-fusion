"""
Vector store CRUD and table operations.

Add, delete, count, index creation, table/schema operations.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from omni.foundation.services.embedding import get_embedding_service

if TYPE_CHECKING:
    from .store import VectorStoreClient

logger = structlog.get_logger(__name__)


async def add(
    client: VectorStoreClient,
    content: str,
    metadata: dict[str, Any] | None,
    collection: str,
) -> bool:
    """Add one document to the vector store."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        service = get_embedding_service()
        vector = service.embed(content)[0]
        doc_id = str(uuid.uuid4())
        ids = [doc_id]
        vectors = [vector]
        contents = [content]
        metadatas = [json.dumps(metadata or {})]
        await store.add_documents(collection, ids, vectors, contents, metadatas)
        client.invalidate_cache(collection)
        return True
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug("VectorStore: Collection %r not found for add operation", collection)
            return False
        logger.error("Add failed", error=str(e))
        return False


async def add_batch(
    client: VectorStoreClient,
    chunks: list[str],
    metadata: list[dict[str, Any]],
    collection: str,
    batch_size: int,
    max_concurrent_embed_batches: int,
) -> int:
    """Batch add documents. Returns number of stored chunks."""
    import asyncio

    store = client._get_store_for_collection(collection)
    if not store or not chunks:
        return 0
    service = get_embedding_service()
    batches = [
        (i, chunks[i : i + batch_size], metadata[i : i + batch_size])
        for i in range(0, len(chunks), batch_size)
    ]

    async def _embed_one(
        batch_idx: int, batch_chunks: list[str], batch_meta: list[dict]
    ) -> tuple[int, list[list[float]], list[str], list[dict]]:
        embeddings = await asyncio.to_thread(service.embed_batch, batch_chunks)
        return (batch_idx, embeddings, batch_chunks, batch_meta)

    try:
        if max_concurrent_embed_batches <= 1:
            results = []
            for batch_idx, batch_chunks, batch_meta in batches:
                _, embeddings, bc, bm = await _embed_one(batch_idx, batch_chunks, batch_meta)
                results.append((batch_idx, embeddings, bc, bm))
        else:
            sem = asyncio.Semaphore(max_concurrent_embed_batches)

            async def _embed_with_sem(
                batch_idx: int, batch_chunks: list[str], batch_meta: list[dict]
            ):
                async with sem:
                    return await _embed_one(batch_idx, batch_chunks, batch_meta)

            tasks = [_embed_with_sem(batch_idx, bc, bm) for batch_idx, bc, bm in batches]
            results = await asyncio.gather(*tasks)
            results = [(r[0], r[1], r[2], r[3]) for r in results]
            results.sort(key=lambda r: r[0])

        chunks_stored = 0
        for batch_num, (_, embeddings, batch_chunks, batch_meta) in enumerate(results, 1):
            ids = [str(uuid.uuid4()) for _ in batch_chunks]
            metadatas = [json.dumps(m or {}) for m in batch_meta]
            await store.add_documents(collection, ids, embeddings, batch_chunks, metadatas)
            chunks_stored += len(batch_chunks)
            logger.info("Batch stored", batch=batch_num, stored=chunks_stored, total=len(chunks))
        client.invalidate_cache(collection)
        return chunks_stored
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug("VectorStore: Collection %r not found for batch add", collection)
            return 0
        logger.error("Batch add failed", error=str(e))
        return 0


async def delete(client: VectorStoreClient, id: str, collection: str) -> bool:
    """Delete one document by id."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        store.delete_by_ids(collection, [id])
        client.invalidate_cache(collection)
        return True
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug("VectorStore: Collection %r not found for delete operation", collection)
            return False
        logger.error("Delete failed", error=str(e))
        return False


async def delete_by_metadata_source(client: VectorStoreClient, collection: str, source: str) -> int:
    """Delete rows whose metadata.source equals or ends with source.

    Used for idempotent ingest: delete existing chunks before re-ingesting.
    Returns number of rows deleted.
    """
    store = client._get_store_for_collection(collection)
    if not store:
        return 0
    if not hasattr(store, "delete_by_metadata_source"):
        logger.debug("Store does not support delete_by_metadata_source")
        return 0
    try:
        deleted = store.delete_by_metadata_source(collection, source)
        if deleted > 0:
            client.invalidate_cache(collection)
        return deleted
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug("VectorStore: Collection %r not found for delete by source", collection)
            return 0
        logger.error("Delete by metadata source failed", error=str(e))
        return 0


async def count(client: VectorStoreClient, collection: str) -> int:
    """Return number of rows in collection."""
    store = client._get_store_for_collection(collection)
    if not store:
        return 0
    try:
        return store.count(collection)
    except Exception as e:
        if client._is_table_not_found(e):
            return 0
        logger.error("Count failed", error=str(e))
        return 0


async def create_index(client: VectorStoreClient, collection: str) -> bool:
    """Create IVF-FLAT index for collection."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        await store.create_index_for_table(collection)
        return True
    except Exception as e:
        logger.error("Create index failed", error=str(e))
        return False


async def get_table_info(client: VectorStoreClient, collection: str) -> dict[str, Any] | None:
    """Get table metadata."""
    store = client._get_store_for_collection(collection)
    if not store:
        return None
    try:
        raw = store.get_table_info(collection)
        return json.loads(raw) if raw else None
    except Exception as e:
        if client._is_table_not_found(e):
            return None
        logger.error("Get table info failed", error=str(e))
        return None


async def list_versions(client: VectorStoreClient, collection: str) -> list[dict[str, Any]]:
    """List historical versions for collection."""
    store = client._get_store_for_collection(collection)
    if not store:
        return []
    try:
        raw = store.list_versions(collection)
        return json.loads(raw) if raw else []
    except Exception as e:
        if client._is_table_not_found(e):
            return []
        logger.error("List versions failed", error=str(e))
        return []


async def get_fragment_stats(client: VectorStoreClient, collection: str) -> list[dict[str, Any]]:
    """Get fragment-level stats."""
    store = client._get_store_for_collection(collection)
    if not store:
        return []
    try:
        raw = store.get_fragment_stats(collection)
        return json.loads(raw) if raw else []
    except Exception as e:
        if client._is_table_not_found(e):
            return []
        logger.error("Get fragment stats failed", error=str(e))
        return []


async def add_columns(
    client: VectorStoreClient,
    collection: str,
    columns: list[dict[str, Any]],
    invalidate_cache: bool,
) -> bool:
    """Add columns (schema evolution)."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        await store.add_columns(collection, columns)
        if invalidate_cache:
            client.invalidate_cache(collection)
        return True
    except Exception as e:
        logger.error("Add columns failed", error=str(e))
        return False


async def alter_columns(
    client: VectorStoreClient,
    collection: str,
    alterations: list[dict[str, Any]],
    invalidate_cache: bool,
) -> bool:
    """Alter columns (schema evolution)."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        await store.alter_columns(collection, alterations)
        if invalidate_cache:
            client.invalidate_cache(collection)
        return True
    except Exception as e:
        logger.error("Alter columns failed", error=str(e))
        return False


async def drop_columns(
    client: VectorStoreClient,
    collection: str,
    columns: list[str],
    invalidate_cache: bool,
) -> bool:
    """Drop columns (schema evolution)."""
    store = client._get_store_for_collection(collection)
    if not store:
        return False
    try:
        await store.drop_columns(collection, columns)
        if invalidate_cache:
            client.invalidate_cache(collection)
        return True
    except Exception as e:
        logger.error("Drop columns failed", error=str(e))
        return False
