# agent/core/vector_store/search.py
"""
Search operations for vector store.

Provides semantic search, hybrid search, and tool search functionality.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .connection import VectorMemory, _get_logger, _get_omni_vector
from .embed import embed_query


async def search(
    self: VectorMemory,
    query: str,
    n_results: int = 5,
    collection: str | None = None,
    where_filter: Dict[str, str] | None = None,
) -> list:
    """
    Search the vector store for similar documents.

    Args:
        self: VectorMemory instance
        query: The search query (will be embedded)
        n_results: Number of results to return
        collection: Optional table name (defaults to project_knowledge)
        where_filter: Optional metadata filter (e.g., {"domain": "python"})

    Returns:
        List of SearchResult objects sorted by similarity
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for search")
        return []

    table_name = self._get_table_name(collection)

    try:
        # Generate embedding for query (use FastEmbed or placeholder)
        query_vector = embed_query(query)
        if query_vector is None:
            return []

        # Perform similarity search (with or without filter)
        if where_filter:
            # Use search_filtered when filter is provided
            filter_json = json.dumps(where_filter)
            results = store.search_filtered(table_name, query_vector, n_results, filter_json)
        else:
            results = store.search(table_name, query_vector, n_results)

        if not results:
            return []

    except Exception as e:
        # Handle table not found or other errors gracefully
        error_str = str(e).lower()
        if "table not found" in error_str:
            _get_logger().debug(
                f"Vector store table '{table_name}' not found, returning empty results"
            )
            return []
        # Re-raise other errors
        raise

    # Parse JSON results
    from .connection import SearchResult

    search_results: list = []
    for json_str in results:
        try:
            result = json.loads(json_str)
            search_results.append(
                SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    distance=result.get("distance", 0.0),
                    id=result.get("id", ""),
                )
            )
        except json.JSONDecodeError:
            continue

    _get_logger().info(
        "Vector search completed",
        query=query[:50],
        results=len(search_results),
    )

    return search_results


async def search_tools_hybrid(
    self: VectorMemory,
    query: str,
    keywords: list[str] | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """
    Search tools using hybrid search (vector + keywords).

    Intent-Driven Tool Loading

    This method combines:
    - Vector similarity search (semantic matching)
    - Keyword boosting (exact term matching)

    Args:
        self: VectorMemory instance
        query: Natural language query describing what the user needs.
        keywords: Optional explicit keywords to boost relevance.
                 Example: ["git", "commit"] for git commit related tools.
        limit: Maximum number of results to return (default: 15, max: 50).

    Returns:
        List of tool dictionaries with keys:
        - id: Tool name (e.g., "git.commit")
        - content: Tool description
        - metadata: Tool metadata dict with keys:
            - skill_name: Parent skill name
            - tool_name: Function name
            - file_path: Source file path
            - input_schema: JSON string of tool schema
            - keywords: List of indexed keywords
            - docstring: Function docstring
        - distance: Hybrid score (lower = better match)

    Example:
        results = await vm.search_tools_hybrid(
            "git commit changes",
            keywords=["git", "commit"],
            limit=10
        )
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for search_tools_hybrid")
        return []

    keywords = keywords or []
    table_name = "skills"

    try:
        # Generate embedding for query
        query_vector = embed_query(query)
        if query_vector is None:
            return []

        # Perform hybrid search (Rust side)
        if hasattr(store, "search_hybrid"):
            results = store.search_hybrid(table_name, query_vector, keywords, limit)
        else:
            # Fallback to regular search if hybrid not available
            results = store.search(table_name, query_vector, limit)

        if not results:
            return []

        # Parse results
        parsed_results: list[dict[str, Any]] = []
        for json_str in results:
            try:
                result = json.loads(json_str)
                parsed_results.append(
                    {
                        "id": result.get("id", ""),
                        "content": result.get("content", ""),
                        "metadata": result.get("metadata", {}),
                        "distance": result.get("distance", 1.0),
                    }
                )
            except json.JSONDecodeError:
                continue

        _get_logger().info(
            "Hybrid tool search completed",
            query=query[:50],
            keywords=keywords,
            results=len(parsed_results),
        )

        return parsed_results

    except Exception as e:
        _get_logger().error("search_tools_hybrid failed", error=str(e))
        return []


async def search_knowledge_hybrid(
    self: VectorMemory,
    query: str,
    keywords: list[str] | None = None,
    limit: int = 5,
    table_name: str = "knowledge",
) -> list[dict[str, Any]]:
    """
    Search project knowledge using hybrid search (vector + keywords).

    The Knowledge Matrix - Knowledge Search

    This method searches the knowledge base (docs, specs, memory)
    for relevant information based on user queries.

    Args:
        self: VectorMemory instance
        query: Natural language query describing what information is needed.
        keywords: Optional explicit keywords to boost relevance.
                 Example: ["git", "commit", "规范"] for git commit rules.
        limit: Maximum number of results (default: 5).
        table_name: Table to search (default: "knowledge").

    Returns:
        List of knowledge chunk dictionaries with keys:
        - id: Chunk ID (e.g., "docs/workflow.md#chunk-2")
        - content: Full chunk text content
        - preview: Truncated preview
        - distance: Similarity score (lower = better)
        - metadata: Dict with doc_path, title, section, etc.

    Example:
        results = await vm.search_knowledge_hybrid(
            "我们的 git commit 规范是什么",
            keywords=["git", "commit", "规范"],
            limit=3
        )
    """
    store = self._ensure_store()
    if not store:
        _get_logger().warning("Vector memory not available for search_knowledge_hybrid")
        return []

    keywords = keywords or []

    try:
        # Generate embedding for query
        query_vector = embed_query(query)
        if query_vector is None:
            return []

        # Perform hybrid search
        if hasattr(store, "search_hybrid"):
            results = store.search_hybrid(table_name, query_vector, keywords, limit)
        else:
            # Fallback to regular search
            results = store.search(table_name, query_vector, limit)

        if not results:
            return []

        # Parse results
        parsed_results: list[dict[str, Any]] = []
        for json_str in results:
            try:
                result = json.loads(json_str)
                # Parse metadata
                metadata = result.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}

                parsed_results.append(
                    {
                        "id": result.get("id", ""),
                        "content": result.get("content", ""),
                        "preview": result.get("preview", result.get("content", "")[:200]),
                        "distance": result.get("distance", 1.0),
                        "metadata": metadata,
                        "doc_id": result.get("doc_id", ""),
                        "doc_path": metadata.get("doc_path", ""),
                        "title": metadata.get("title", ""),
                        "section": metadata.get("section", ""),
                    }
                )
            except json.JSONDecodeError:
                continue

        _get_logger().info(
            "Hybrid knowledge search completed",
            query=query[:50],
            keywords=keywords,
            results=len(parsed_results),
        )

        return parsed_results

    except Exception as e:
        error_str = str(e).lower()
        # Graceful handling for "Table not found" errors
        if "table not found" in error_str:
            _get_logger().debug(
                f"search_knowledge_hybrid: table '{table_name}' not found, returning empty results"
            )
        else:
            _get_logger().error("search_knowledge_hybrid failed", error=str(e))
        return []


# Convenience function for module-level import
async def search_knowledge(query: str, n_results: int = 5, collection: str | None = None) -> list:
    """Search project knowledge base."""
    from .connection import VectorMemory

    return await search(VectorMemory(), query, n_results, collection)
