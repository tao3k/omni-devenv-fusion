"""
Skill Analyzer Module

High-performance skill analytics using PyArrow for columnar operations.

Provides Arrow-native operations for:
- Tool analytics and statistics
- Category distribution analysis
- System context generation
- Documentation coverage reporting

Architecture:
    LanceDB → RustVectorStore.get_analytics_table_sync() → PyArrow Table → Analyzer Functions

Usage:
    from omni.core.skills.analyzer import get_analytics_dataframe, get_category_distribution

    table = get_analytics_dataframe()
    categories = get_category_distribution()
    context = generate_system_context()
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.skills.analyzer")


def get_analytics_dataframe():
    """Get all tools as a PyArrow Table for analytics.

    This method uses the Arrow-native export from Rust bindings
    for high-performance analytics operations.

    Returns:
        PyArrow Table with columns: id, content, skill_name, tool_name,
        file_path, routing_keywords, etc.

    Raises:
        ImportError: If pyarrow is not installed
        RuntimeError: If LanceDB is not available
    """
    try:
        import pyarrow as pa
    except ImportError as err:
        raise ImportError(
            "pyarrow is required for analytics. Install with: pip install pyarrow"
        ) from err

    try:
        from omni.foundation.bridge.rust_vector import get_vector_store

        store = get_vector_store()

        # Use the Arrow-optimized sync export; avoids asyncio.run() in active loops.
        table = store.get_analytics_table_sync()

        # Ensure it's a PyArrow Table
        if table is not None and not isinstance(table, pa.Table):
            # It's a Python object, convert if possible
            with suppress(Exception):
                table = pa.Table.from_pydict(table)

        return table
    except Exception as err:
        raise RuntimeError(f"Failed to get analytics table from LanceDB: {err}") from err


def generate_system_context(limit: int | None = None) -> str:
    """Generate system context using Arrow vectorized operations.

    This is optimized for generating tool context for LLM prompts.
    Uses PyArrow Compute for efficient string operations.

    Args:
        limit: Optional limit on number of tools to include

    Returns:
        Formatted string with all tools in @omni() format
    """
    table = get_analytics_dataframe()

    if table is None or table.num_rows == 0:
        return ""

    # Use PyArrow for vectorized string operations
    try:
        # Vectorized formatting: "@omni(name)" format
        ids = table["id"]
        contents = table["content"]

        # Create formatted tool calls
        formatted_tools = [f'@omni("{id_}")' for id_ in ids.to_pylist()]

        # Combine with descriptions
        lines = [
            f"{tool} - {desc}"
            for tool, desc in zip(formatted_tools, contents.to_pylist(), strict=False)
        ]
    except Exception:
        # Fallback to simple iteration if PyArrow Compute fails
        lines = []
        for row in table.to_pylist():
            tool_id = row.get("id", "unknown")
            content = row.get("content", "")
            lines.append(f'@omni("{tool_id}") - {content}')

    if limit and len(lines) > limit:
        lines = lines[:limit]

    return "\n".join(lines)


def get_category_distribution() -> dict[str, int]:
    """Get tool count distribution by category using Arrow.

    Returns:
        Dictionary mapping category names to tool counts
    """
    table = get_analytics_dataframe()

    if table is None or table.num_rows == 0:
        return {}

    try:
        import pyarrow.compute as pc

        # Use PyArrow value_counts for efficient grouping
        if "skill_name" in table.column_names:
            skill_names = table["skill_name"]
        elif "category" in table.column_names:
            skill_names = table["category"]
        else:
            return {}

        # Get value counts
        try:
            result = pc.value_counts(skill_names)
            counts = result["counts"].to_pylist()
            unique = result["values"].to_pylist()
            return dict(zip(unique, counts, strict=False))
        except Exception:
            # Fallback if value_counts fails
            pass
    except ImportError:
        pass

    # Fallback to Python iteration
    categories: dict[str, int] = {}
    for row in table.to_pylist():
        cat = row.get("skill_name") or row.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    return categories


def analyze_tools(
    category: str | None = None,
    missing_docs: bool = False,
) -> dict[str, Any]:
    """Analyze tools with optional filters.

    Args:
        category: Filter by skill category
        missing_docs: Only return tools without documentation

    Returns:
        Dictionary with analysis results including:
        - table: PyArrow Table (filtered)
        - total_tools: Total tool count
        - missing_documentation: Count of tools without docs
        - category_distribution: Category counts
    """
    table = get_analytics_dataframe()

    if table is None or table.num_rows == 0:
        return {
            "table": None,
            "total_tools": 0,
            "missing_documentation": 0,
            "category_distribution": {},
        }

    # Apply category filter
    if category:
        try:
            mask = table["skill_name"] == category
            table = table.filter(mask)
        except Exception:
            # Fallback: filter by string matching
            ids = table["id"].to_pylist()
            mask = [category in id_ for id_ in ids]
            import pyarrow as pa

            table = table.filter(pa.array(mask))

    # Apply missing docs filter
    if missing_docs:
        try:
            contents = table["content"].to_pylist()
            import pyarrow as pa

            mask = [not c or c.strip() == "" for c in contents]
            table = table.filter(pa.array(mask))
        except Exception:
            pass

    # Get missing docs count
    missing_count = 0
    if "content" in table.column_names:
        try:
            contents = table["content"].to_pylist()
            missing_count = sum(1 for c in contents if not c or c.strip() == "")
        except Exception:
            pass

    return {
        "table": table,
        "total_tools": table.num_rows,
        "missing_documentation": missing_count,
        "category_distribution": get_category_distribution(),
    }


__all__ = [
    "analyze_tools",
    "generate_system_context",
    "get_analytics_dataframe",
    "get_category_distribution",
]
