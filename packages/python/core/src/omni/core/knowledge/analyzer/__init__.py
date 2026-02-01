"""
Knowledge Analyzer Module - PyArrow-Native Knowledge Analytics

Provides high-performance analytics for the knowledge base using PyArrow.
"""

from __future__ import annotations

from typing import Any
import asyncio

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.knowledge.analyzer")


def get_knowledge_dataframe(collection: str = "knowledge"):
    """Get all knowledge entries as a PyArrow Table for analytics.

    Returns:
        PyArrow Table with available columns (id, content, source, type, etc.)
    """
    try:
        import pyarrow as pa
    except ImportError:
        raise ImportError("pyarrow is required for analytics. Install with: pip install pyarrow")

    try:
        from omni.agent.cli.commands.reindex import get_database_path

        # Librarian uses collection.lance by default for storage path
        storage_path = get_database_path("knowledge")

        from omni.foundation.bridge.rust_vector import get_vector_store

        store = get_vector_store(index_path=storage_path)

        # Get all entries as list of dicts
        entries = asyncio.run(store.list_all(collection))

        if not entries:
            return None

        # Convert to PyArrow Table
        return pa.Table.from_pylist(entries)
    except Exception as e:
        raise RuntimeError(f"Failed to get knowledge analytics table: {e}")


def get_type_distribution(collection: str = "knowledge") -> dict[str, int]:
    """Get distribution of knowledge entries by type."""
    table = get_knowledge_dataframe(collection)
    if table is None or table.num_rows == 0:
        return {}

    if "type" not in table.column_names:
        return {"unknown": table.num_rows}

    try:
        import pyarrow.compute as pc

        result = pc.value_counts(table["type"])
        return dict(zip(result.field("values").to_pylist(), result.field("counts").to_pylist()))
    except Exception:
        # Fallback
        types: dict[str, int] = {}
        for t in table["type"].to_pylist():
            t = t or "unknown"
            types[t] = types.get(t, 0) + 1
        return types


def get_source_distribution(
    collection: str = "knowledge", limit: int | None = None
) -> dict[str, int]:
    """Get distribution of knowledge entries by source.

    Args:
        collection: Collection to analyze
        limit: Optional limit on number of sources to return
    """
    table = get_knowledge_dataframe(collection)
    if table is None or table.num_rows == 0:
        return {}

    if "source" not in table.column_names:
        logger.warning(f"Column 'source' not found in table. Columns: {table.column_names}")
        return {}

    try:
        import pyarrow.compute as pc

        result = pc.value_counts(table["source"])

        # Sort by count descending using Python sorting
        sources = result.field("values").to_pylist()
        counts = result.field("counts").to_pylist()

        combined = sorted(zip(sources, counts), key=lambda x: x[1], reverse=True)

        if limit:
            combined = combined[:limit]

        return dict(combined)
    except Exception as e:
        logger.error(f"Error in get_source_distribution: {e}")
        return {}


def analyze_knowledge(collection: str = "knowledge", limit: int | None = None) -> dict[str, Any]:
    """Perform comprehensive analysis of the knowledge base.

    Args:
        collection: Collection to analyze
        limit: Optional limit for source distribution (None = all)
    """
    table = get_knowledge_dataframe(collection)

    if table is None or table.num_rows == 0:
        return {
            "total_entries": 0,
            "type_distribution": {},
            "source_distribution": {},
            "total_size_bytes": 0,
            "avg_content_length": 0,
        }

    total_entries = table.num_rows
    type_dist = get_type_distribution(collection)
    source_dist = get_source_distribution(collection, limit=limit)

    # Calculate content statistics if content column exists
    avg_len = 0
    total_size = 0
    if "content" in table.column_names:
        import pyarrow.compute as pc

        content_lens = pc.utf8_length(table["content"])
        total_size = pc.sum(content_lens).as_py() or 0
        avg_len = total_size / total_entries if total_entries > 0 else 0

    return {
        "total_entries": total_entries,
        "type_distribution": type_dist,
        "source_distribution": source_dist,
        "total_size_bytes": total_size,
        "avg_content_length": avg_len,
        "column_names": table.column_names,
    }


__all__ = [
    "get_knowledge_dataframe",
    "get_type_distribution",
    "get_source_distribution",
    "analyze_knowledge",
]
