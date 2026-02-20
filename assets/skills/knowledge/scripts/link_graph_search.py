"""
LinkGraph Search Skill - Unified search + link graph/vector helpers.

Commands:
- search: Unified entry (mode=hybrid|keyword|link_graph|vector); default hybrid.
- link_graph_refresh_index: Trigger common delta/full index refresh (debug/ops).
- link_graph_toc: Table of Contents for LLM context
- link_graph_stats: Knowledge base statistics
- link_graph_links: Notes linked to/from a note
- link_graph_find_related: Related notes by link distance
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command, skill_resource
from omni.foundation.api.response_payloads import build_error_response
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.knowledge.link_graph_search")


def _resolve_paths(paths: ConfigPaths | None = None) -> ConfigPaths:
    return paths if paths is not None else ConfigPaths()


def _get_link_graph_backend(paths: ConfigPaths | None = None) -> Any:
    resolved_paths = _resolve_paths(paths)
    from omni.rag.link_graph import get_link_graph_backend

    return get_link_graph_backend(notebook_dir=str(resolved_paths.project_root))


# =============================================================================
# Skill Resources (read-only data via omni://skill/knowledge/*)
# =============================================================================


@skill_resource(
    name="link_graph_stats",
    description="Link graph statistics: total notes, orphans, linked notes",
    resource_uri="omni://skill/knowledge/link_graph_stats",
)
async def link_graph_stats_resource() -> dict:
    """LinkGraph knowledge base statistics as a resource."""
    try:
        backend = _get_link_graph_backend()
        return await backend.stats()
    except Exception as e:
        return build_error_response(error=str(e))


@skill_resource(
    name="link_graph_toc",
    description="Link graph table of contents (titles and paths)",
    resource_uri="omni://skill/knowledge/link_graph_toc",
)
async def link_graph_toc_resource() -> dict:
    """LinkGraph table of contents as a resource."""
    try:
        backend = _get_link_graph_backend()
        notes = await backend.toc(limit=1000)
        return {
            "total": len(notes),
            "notes": [
                {"title": str(item.get("title") or ""), "path": str(item.get("path") or "")}
                for item in notes
            ],
        }
    except Exception as e:
        return build_error_response(error=str(e))


@skill_command(
    name="link_graph_toc",
    category="search",
    description="""
    Get Table of Contents (all notes) for LLM context.

    Returns a JSON structure containing all notes with their:
    - ID (filename stem)
    - Title
    - Tags
    - Lead excerpt

    This is useful for providing the LLM with an overview of the knowledge base.
    """,
    autowire=True,
)
async def link_graph_toc(
    paths: ConfigPaths | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Get Table of Contents for LLM context."""
    try:
        backend = _get_link_graph_backend(paths)
        notes_all = await backend.toc(limit=max(1000, int(limit)))
        notes = notes_all[:limit]
        total = len(notes_all)

        return {
            "success": True,
            "total": total,
            "returned": len(notes),
            "notes": notes,
        }
    except Exception as e:
        logger.error(f"LinkGraph TOC failed: {e}")
        raise


def _get_run_search():
    """Resolve run_search so it works from CLI (scripts path may be removed after load)."""
    try:
        from search import run_search

        return run_search
    except ImportError:
        pass
    # Fallback: load search package from same directory as this file (CLI / MCP)
    this_dir = Path(__file__).resolve().parent
    if str(this_dir) not in sys.path:
        sys.path.insert(0, str(this_dir))
    try:
        from search import run_search

        return run_search
    except ImportError:
        spec = importlib.util.spec_from_file_location("search", this_dir / "search" / "__init__.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.run_search
    raise ImportError("Could not import run_search from search package")


async def _run_unified_search(
    query: str,
    mode: str = "hybrid",
    max_results: int = 10,
    scope: str = "all",
    use_hybrid: bool = True,
    search_options: dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Shared implementation for search and unified_search."""
    run_search = _get_run_search()
    return await run_search(
        query=query,
        mode=mode,
        max_results=max_results,
        scope=scope,
        use_hybrid=use_hybrid,
        search_options=search_options,
        paths=paths,
    )


@skill_command(
    name="search",
    category="search",
    description="""
    Unified knowledge search. Single entry point for all search needs.

    Default (mode=hybrid): LinkGraph reasoning + vector fallback (recommended).
    Use mode to force keyword-only, link-graph-only, or vector-only.

    Args:
        - query: str - Search query (required)
        - mode: str = "hybrid" - "hybrid" (link_graph+vector), "keyword" (ripgrep), "link_graph" (links only), "vector" (semantic only)
        - max_results: int = 10 - Maximum results (hybrid/link_graph/vector)
        - scope: str = "all" - For mode=keyword: "docs", "references", "skills", "harvested", or "all"
        - use_hybrid: bool = True - For mode=hybrid: use vector fallback
        - search_options: dict | None - For mode=link_graph, strict v2 options payload:
          {"schema":"omni.link_graph.search_options.v2","match_strategy":"fts|exact|re","sort_terms":[...],"filters":{...}}

    Returns:
        Search results (shape depends on mode).
    """,
    autowire=True,
)
async def search(
    query: str,
    mode: str = "hybrid",
    max_results: int = 10,
    scope: str = "all",
    use_hybrid: bool = True,
    search_options: dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Unified search: delegates to search package."""
    return await _run_unified_search(
        query=query,
        mode=mode,
        max_results=max_results,
        scope=scope,
        use_hybrid=use_hybrid,
        search_options=search_options,
        paths=paths,
    )


@skill_command(
    name="unified_search",
    category="search",
    description="""
    Same as knowledge.search: unified knowledge search (link_graph + keyword + vector).

    Use this when knowledge.search triggers client validation errors.
    Args: query (required), mode (hybrid|keyword|link_graph|vector), max_results, scope,
    use_hybrid, and optional search_options (strict v2 schema for link_graph mode).
    """,
    autowire=True,
)
async def unified_search(
    query: str,
    mode: str = "hybrid",
    max_results: int = 10,
    scope: str = "all",
    use_hybrid: bool = True,
    search_options: dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Alias for search; same implementation."""
    return await _run_unified_search(
        query=query,
        mode=mode,
        max_results=max_results,
        scope=scope,
        use_hybrid=use_hybrid,
        search_options=search_options,
        paths=paths,
    )


@skill_command(
    name="link_graph_search",
    category="search",
    description="""
    LinkGraph-only search over notebook links and structure.

    This is equivalent to knowledge.search with mode="link_graph".
    Use search_options (strict v2 schema payload) to control match strategy, sort terms, and filters.
    """,
    autowire=True,
)
async def link_graph_search(
    query: str,
    max_results: int = 10,
    search_options: dict[str, Any] | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Explicit LinkGraph-only search command."""
    return await _run_unified_search(
        query=query,
        mode="link_graph",
        max_results=max_results,
        scope="all",
        use_hybrid=False,
        search_options=search_options,
        paths=paths,
    )


@skill_command(
    name="link_graph_hybrid_search",
    category="search",
    description="""
    Hybrid search (link graph first + vector fallback).

    This is equivalent to knowledge.search with mode="hybrid".
    """,
    autowire=True,
)
async def link_graph_hybrid_search(
    query: str,
    max_results: int = 10,
    use_hybrid: bool = True,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Explicit hybrid search command."""
    return await _run_unified_search(
        query=query,
        mode="hybrid",
        max_results=max_results,
        scope="all",
        use_hybrid=use_hybrid,
        paths=paths,
    )


@skill_command(
    name="link_graph_stats",
    category="info",
    description="""
    Get knowledge base statistics from the link graph notebook.

    Returns:
    - Total notes
    - Orphans (unlinked notes)
    - Graph statistics
    """,
    autowire=True,
)
async def link_graph_stats(
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Get LinkGraph knowledge base statistics via common backend cache policy."""
    try:
        backend = _get_link_graph_backend(paths)
        stats = await backend.stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"LinkGraph stats failed: {e}")
        raise


@skill_command(
    name="link_graph_refresh_index",
    category="maintenance",
    description="""
    Trigger LinkGraph index refresh through the common backend API.

    Use this for debugging/operations when you want explicit delta/full refresh,
    and to inspect monitor phases with `omni skill run ... -v`.

    Args:
        - changed_paths: list[str] | None - Changed paths for delta refresh.
        - force_full: bool = False - Force full rebuild regardless of delta size.

    Returns:
        Refresh mode + change count + fallback flags from common backend contract.
    """,
    autowire=True,
)
async def link_graph_refresh_index(
    changed_paths: list[str] | None = None,
    force_full: bool = False,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Refresh link graph index via common backend delta/full strategy."""
    backend = _get_link_graph_backend(paths)
    result = await backend.refresh_with_delta(changed_paths, force_full=force_full)

    changed: list[str] = []
    if isinstance(changed_paths, list):
        changed = [str(item) for item in changed_paths if str(item or "").strip()]

    payload: dict[str, Any] = {"success": True, "changed_paths": changed}
    if isinstance(result, dict):
        payload.update(result)
    else:
        payload["result"] = result
    return payload


@skill_command(
    name="link_graph_links",
    category="search",
    description="""
    Find notes that are linked to/from a specific note.

    Args:
        - note_id: str - Note ID / filename stem (required)
        - direction: str - "to" (notes linking TO this), "from" (notes linked BY this), "both" (default)

    Returns:
        Lists of incoming and outgoing links.
    """,
    autowire=True,
)
async def link_graph_links(
    note_id: str,
    direction: str = "both",
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Find notes linked to/from a specific note."""
    try:
        link_graph = importlib.import_module("omni.rag.link_graph")
        backend = _get_link_graph_backend(paths)
        neighbors = await backend.neighbors(
            note_id,
            direction=link_graph.normalize_link_graph_direction(direction),
            hops=1,
            limit=200,
        )
        outgoing, incoming = link_graph.neighbors_to_link_rows(neighbors)

        return {
            "success": True,
            "note_id": note_id,
            "direction": direction,
            "incoming": incoming,
            "outgoing": outgoing,
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
        }
    except Exception as e:
        logger.error(f"LinkGraph links failed: {e}")
        raise


@skill_command(
    name="link_graph_find_related",
    category="search",
    description="""
    Find notes related to a given note using link-graph traversal.

    Args:
        - note_id: str - Starting note ID (required)
        - max_distance: int - Maximum link distance (default: 2)
        - limit: int - Maximum results (default: 20)

    Returns:
        List of related notes with distance information.
    """,
    autowire=True,
)
async def link_graph_find_related(
    note_id: str,
    max_distance: int = 2,
    limit: int = 20,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Find notes related to a given note."""
    try:
        backend = _get_link_graph_backend(paths)
        related = await backend.related(note_id, max_distance=max_distance, limit=limit)

        return {
            "success": True,
            "note_id": note_id,
            "max_distance": max_distance,
            "total": len(related),
            "results": [
                {
                    "id": str(getattr(n, "stem", "") or ""),
                    "title": str(getattr(n, "title", "") or ""),
                    "path": str(getattr(n, "path", "") or ""),
                }
                for n in related
            ],
        }
    except Exception as e:
        logger.error(f"LinkGraph find_related failed: {e}")
        raise


__all__ = [
    "link_graph_find_related",
    "link_graph_hybrid_search",
    "link_graph_links",
    "link_graph_refresh_index",
    "link_graph_search",
    "link_graph_stats",
    "link_graph_toc",
    "search",
    "unified_search",
]
