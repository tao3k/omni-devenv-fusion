"""
Unified knowledge search package.

Single entry: run_search(query, mode=...) dispatches to:
- keyword: ripgrep over docs/references/skills/harvested
- link_graph: link graph reasoning only
- vector: semantic/recall over LanceDB
- hybrid: link graph + vector (default)

Completeness: every mode returns a dict with at least "query" and mode-specific keys;
hybrid/link_graph/vector include "success": True.
"""

from __future__ import annotations

from typing import Any

from omni.foundation.config.paths import ConfigPaths

from .hybrid import run_hybrid_search
from .keyword import search_keyword
from .link_graph import run_link_graph_search
from .vector import run_vector_search

SEARCH_MODES = ("hybrid", "keyword", "link_graph", "vector")


async def run_search(
    query: str,
    mode: str = "hybrid",
    max_results: int = 10,
    scope: str = "all",
    use_hybrid: bool = True,
    search_options: dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Unified search dispatch. Returns dict with success, query, and mode-specific payload."""
    if paths is None:
        paths = ConfigPaths()
    mode = (mode or "hybrid").strip().lower()

    if mode == "keyword":
        return search_keyword(query, scope=scope, paths=paths)

    if mode == "link_graph":
        return await run_link_graph_search(
            query,
            max_results=max_results,
            search_options=search_options,
            paths=paths,
        )

    if mode == "vector":
        return await run_vector_search(
            query, limit=max_results, collection="knowledge_chunks", paths=paths
        )

    # default: hybrid
    return await run_hybrid_search(
        query=query,
        max_results=max_results,
        use_hybrid=use_hybrid,
        paths=paths,
    )


__all__ = [
    "SEARCH_MODES",
    "run_hybrid_search",
    "run_link_graph_search",
    "run_search",
    "run_vector_search",
    "search_keyword",
]
