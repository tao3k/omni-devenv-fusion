"""
External Dependency Search - Search symbols in external crate dependencies.

Provides fast API lookup for external dependencies using Rust-powered indexer.

Use Cases:
- LLM doesn't know new API after dependency upgrade
- Need to find exact function signature
- Want to avoid reading cargo registry source files (token waste)
- Unified search across project + external symbols

Commands:
- dependency_search: Search symbols (external or unified with project)
- dependency_status: Check indexed external dependencies
- dependency_build: Build the dependency index
- dependency_list: List all indexed dependencies

Resources:
- dependency_index: Indexed crates and symbol counts

Workflow:
    # 1. When Cargo.toml dependency is upgraded
    omni sync symbols

    # 2. LLM queries new API (external only)
    @dependency_search "tokio spawn"

    # 3. Unified search (project + external)
    @dependency_search "spawn" {"mode": "unified"}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command, skill_resource
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.knowledge.dependency")


@skill_resource(
    name="dependency_index",
    description="Indexed external crate dependencies and symbol counts",
    resource_uri="omni://skill/knowledge/dependency_index",
)
def dependency_index_resource() -> dict:
    """Dependency index summary as a resource."""
    try:
        from omni.foundation.config.skills import SKILLS_DIR

        index_dir = SKILLS_DIR().parent.parent / ".cache" / "dep-index"
        if not index_dir.exists():
            return {"indexed_crates": 0, "total_symbols": 0}

        crates = sorted(d.name for d in index_dir.iterdir() if d.is_dir())
        total = 0
        for crate_dir in index_dir.iterdir():
            if crate_dir.is_dir():
                for f in crate_dir.glob("*.json"):
                    total += 1
        return {"indexed_crates": len(crates), "total_symbols": total, "crates": crates}
    except Exception as e:
        return {"error": str(e)}


def _get_project_root() -> str:
    """Get the project root directory."""
    return os.environ.get("OMNI_PROJECT_ROOT", str(Path.cwd()))


def _get_config_path() -> str | None:
    """Get the references.yaml config path."""
    candidates = [
        "assets/references.yaml",
        os.environ.get("OMNI_REFERENCES_YAML"),
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


@skill_command(
    name="dependency_search",
    category="search",
    description="""
    Search for symbols in external crate dependencies.

    Use this when:
    - A dependency was upgraded and you don't know the new API
    - Need to find exact function signatures
    - Want to avoid reading source files in cargo registry
    - Search across both project and external symbols (mode="unified")

    Args:
        - query: str - Search query for symbols (required)
        - limit: int = 10 - Maximum results
        - crate: str | None = None - Limit to specific crate
        - mode: str = "external" - Search mode: "external" or "unified"

    Returns:
        Dictionary with success, count, results, and indexed crates.

    Examples:
        @dependency_search "spawn"
        @dependency_search "value" {"crate": "serde_json"}
        @dependency_search "spawn" {"mode": "unified"}
        @dependency_search "Arc" {"limit": 20}
    """,
    autowire=True,
)
async def dependency_search(
    query: str,
    limit: int = 10,
    crate: str | None = None,
    mode: str = "external",
) -> dict[str, Any]:
    """Search for symbols in external dependencies or unified (project + external).

    Use this when:
    - A dependency was upgraded and you don't know the new API
    - Need to find exact function signatures
    - Want to avoid reading source files in cargo registry
    - Search across both project and external symbols (mode="unified")

    Args:
        query: Search query for symbols (required).
        limit: Maximum results to return (default: 10, max: 50).
        crate: Optional crate name to limit search scope.
        mode: Search mode - "external" (default) or "unified" (project + external).

    Returns:
        Dictionary with:
        - success: bool - Whether search completed successfully
        - query: str - The search query
        - mode: str - Search mode used
        - crate: str | None - Crate filter if specified
        - count: int - Number of results returned
        - results: list[dict] - Matching symbols with name, kind, source, crate, file, line
        - indexed_crates: list[str] - Available indexed crates

    Examples:
        # Search tokio spawn functions in external deps
        @dependency_search "spawn"

        # Limit to specific crate
        @dependency_search "value" {"crate": "serde_json"}

        # Unified search (project + external)
        @dependency_search "spawn" {"mode": "unified"}

        # Increase result limit
        @dependency_search "Arc" {"limit": 20}
    """
    try:
        from omni_core_rs import PyDependencyIndexer, PyUnifiedSymbolIndex

        project_root = _get_project_root()
        config_path = _get_config_path()

        indexer = PyDependencyIndexer(project_root, config_path)
        indexer.load_index()

        # Unified mode: combine external symbols into unified index
        if mode == "unified":
            unified = PyUnifiedSymbolIndex()

            # Get external symbols
            if crate:
                ext_results = json.loads(indexer.search_crate(crate, query, limit))
            else:
                ext_results = json.loads(indexer.search(query, limit))

            # Add external symbols to unified index
            for r in ext_results:
                unified.add_external_symbol(
                    r.get("name", ""),
                    r.get("kind", "unknown"),
                    f"{r.get('file', '')}:{r.get('line', 0)}",
                    r.get("crate_name", ""),
                )

            # Unified search returns both project and external
            results = json.loads(unified.search_unified_json(query, limit))
        else:
            # External only mode (default)
            if crate:
                results = json.loads(indexer.search_crate(crate, query, limit))
            else:
                results = json.loads(indexer.search(query, limit))

        if not results:
            return {
                "success": True,
                "query": query,
                "mode": mode,
                "count": 0,
                "results": [],
                "message": f"No symbols found for '{query}'.",
                "hint": "Run 'omni sync symbols' to index external dependencies first.",
            }

        formatted = []
        for r in results[:limit]:
            source = r.get("source", "external")
            file_path = r.get("file", r.get("location", ""))
            crate_name = r.get("crate_name", "")

            formatted.append(
                {
                    "name": r.get("name", ""),
                    "kind": r.get("kind", "unknown"),
                    "source": source,  # "project" or "external"
                    "crate": crate_name,
                    "file": file_path.split("/")[-1].split(":")[0] if file_path else "",
                    "line": int(file_path.split(":")[-1]) if ":" in file_path else 0,
                }
            )

        return {
            "success": True,
            "query": query,
            "mode": mode,
            "crate": crate,
            "count": len(formatted),
            "results": formatted,
            "indexed_crates": indexer.get_indexed(),
        }

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return {
            "success": False,
            "error": "PyDependencyIndexer not available",
            "hint": "Ensure omni-core-rs is properly installed",
        }
    except Exception as e:
        logger.error(f"Dependency search failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
        }


@skill_command(
    name="dependency_status",
    category="system",
    description="""
    Check the status of external dependency indexing.

    Shows:
    - Number of indexed crates
    - Total symbols indexed
    - List of indexed crates

    Returns:
        Dictionary with status, counts, and crate list.
    """,
    autowire=True,
)
async def dependency_status() -> dict[str, Any]:
    """Check the status of external dependency indexing.

    Returns:
        Dictionary with:
        - status: str - "ok" or "error"
        - indexed_crates: int - Number of crates indexed
        - total_symbols: int - Total number of symbols indexed
        - indexed_list: list[str] - List of indexed crate names

    Example:
        @dependency_status
    """
    try:
        from omni_core_rs import PyDependencyIndexer

        project_root = _get_project_root()
        config_path = _get_config_path()

        indexer = PyDependencyIndexer(project_root, config_path)
        indexer.load_index()

        stats_json = indexer.stats()
        stats = json.loads(stats_json)

        return {
            "status": "ok",
            "indexed_crates": stats.get("total_crates", 0),
            "total_symbols": stats.get("total_symbols", 0),
            "indexed_list": indexer.get_indexed(),
        }

    except ImportError:
        return {
            "status": "error",
            "error": "PyDependencyIndexer not available",
        }
    except Exception as e:
        logger.error(f"Dependency status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@skill_command(
    name="dependency_build",
    category="system",
    description="""
    Build the external dependency index.

    This parses Cargo.toml dependencies, fetches sources from cargo registry,
    and extracts symbols using omni-tags.

    Run this after:
    - Adding new dependencies
    - Upgrading dependency versions
    - Changes to references.yaml configuration

    Returns:
        Dictionary with build results and statistics.
    """,
    autowire=True,
)
async def dependency_build() -> dict[str, Any]:
    """Build the external dependency index.

    This parses Cargo.toml dependencies, fetches sources from cargo registry,
    and extracts symbols using omni-tags.

    Returns:
        Dictionary with:
        - success: bool - Whether build completed successfully
        - files_processed: int - Number of files processed
        - total_symbols: int - Total symbols extracted
        - errors: int - Number of errors encountered
        - crates_indexed: int - Number of crates indexed
        - indexed_list: list[str] - List of indexed crate names

    Example:
        @dependency_build
    """
    try:
        from omni_core_rs import PyDependencyIndexer

        project_root = _get_project_root()
        config_path = _get_config_path()

        indexer = PyDependencyIndexer(project_root, config_path)
        result_json = indexer.build(True)
        result = json.loads(result_json)

        return {
            "success": True,
            "files_processed": result.get("files_processed", 0),
            "total_symbols": result.get("total_symbols", 0),
            "errors": result.get("errors", 0),
            "crates_indexed": result.get("crates_indexed", 0),
            "indexed_list": indexer.get_indexed(),
        }

    except ImportError:
        return {
            "success": False,
            "error": "PyDependencyIndexer not available",
            "hint": "Ensure omni-core-rs is properly installed",
        }
    except Exception as e:
        logger.error(f"Dependency build failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@skill_command(
    name="dependency_list",
    category="system",
    description="""
    List all indexed external dependencies.

    Shows which crates have been indexed and are available for search.

    Returns:
        Dictionary with count and list of crates.
    """,
    autowire=True,
)
async def dependency_list() -> dict[str, Any]:
    """List all indexed external dependencies.

    Returns:
        Dictionary with:
        - success: bool - Whether operation completed successfully
        - count: int - Number of indexed crates
        - crates: list[str] - List of indexed crate names

    Example:
        @dependency_list
    """
    try:
        from omni_core_rs import PyDependencyIndexer

        project_root = _get_project_root()
        config_path = _get_config_path()

        indexer = PyDependencyIndexer(project_root, config_path)
        indexer.load_index()

        crates = indexer.get_indexed()

        return {
            "success": True,
            "count": len(crates),
            "crates": crates,
        }

    except ImportError:
        return {
            "success": False,
            "error": "PyDependencyIndexer not available",
        }
    except Exception as e:
        logger.error(f"Dependency list failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


__all__ = [
    "dependency_search",
    "dependency_status",
    "dependency_build",
    "dependency_list",
]
