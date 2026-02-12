"""
ZK Search Skill - Reasoning-based Knowledge Retrieval

PageIndex-style high-precision search using Zettelkasten bidirectional links.

Commands:
- zk_search: Search notes using ZK bidirectional links (reasoning-based)
- zk_toc: Get Table of Contents for LLM context
- zk_hybrid_search: Combine ZK + Vector search
- zk_stats: Get knowledge base statistics
- zk_links: Find notes linked to/from a specific note
"""

import json
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

from omni.rag.zk_search import (
    ZkReasoningSearcher,
    ZkSearchConfig,
    ZkHybridSearcher,
)

logger = get_logger("skill.knowledge.zk_search")

# Global searcher instance (lazy initialization)
_zk_searcher: ZkReasoningSearcher | None = None


def _get_searcher(paths: ConfigPaths | None = None) -> ZkReasoningSearcher:
    """Get or create the ZK searcher instance."""
    global _zk_searcher
    if _zk_searcher is None:
        if paths is None:
            paths = ConfigPaths()
        _zk_searcher = ZkReasoningSearcher(
            notebook_dir=str(paths.project_root),
            config=ZkSearchConfig(max_iterations=3, max_notes_per_iteration=10),
        )
    return _zk_searcher


@skill_command(
    name="zk_search",
    category="search",
    description="""
    Search knowledge notes using ZK bidirectional links (PageIndex-style reasoning).

    This is a high-precision search that uses:
    1. Direct keyword matching
    2. Bidirectional link traversal (reasoning loop)
    3. Tag-based filtering

    Args:
        - query: str - Search query (required)
        - max_results: int - Maximum results to return (default: 10)
        - max_iterations: int - Reasoning loop iterations (default: 3)

    Returns:
        List of search results with relevance scores and reasoning.
    """,
    autowire=True,
)
async def zk_search(
    query: str,
    max_results: int = 10,
    max_iterations: int = 3,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Search notes using ZK reasoning-based retrieval."""
    try:
        if paths is None:
            paths = ConfigPaths()

        searcher = ZkReasoningSearcher(
            notebook_dir=str(paths.project_root),
            config=ZkSearchConfig(
                max_iterations=max_iterations,
                max_notes_per_iteration=max_results // max_iterations
                if max_iterations > 0
                else max_results,
            ),
        )

        results = await searcher.search(query, max_results=max_results)

        return {
            "success": True,
            "query": query,
            "total": len(results),
            "results": [
                {
                    "title": r.note.title,
                    "id": r.note.filename_stem,
                    "path": r.note.path,
                    "score": r.relevance_score,
                    "source": r.source,
                    "distance": r.distance,
                    "reasoning": r.reasoning,
                    "lead": r.note.lead[:200] if r.note.lead else "",
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"ZK search failed: {e}")
        raise


@skill_command(
    name="zk_toc",
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
async def zk_toc(
    paths: ConfigPaths | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Get Table of Contents for LLM context."""
    try:
        if paths is None:
            paths = ConfigPaths()

        searcher = _get_searcher(paths)
        toc_json = await searcher.get_toc_for_context()
        toc_data = json.loads(toc_json)

        # Apply limit
        notes = toc_data["notes"][:limit]
        total = len(toc_data["notes"])

        return {
            "success": True,
            "total": total,
            "returned": len(notes),
            "notes": notes,
        }
    except Exception as e:
        logger.error(f"ZK TOC failed: {e}")
        raise


@skill_command(
    name="zk_hybrid_search",
    category="search",
    description="""
    Hybrid search combining ZK reasoning + Vector search fallback.

    Tier 1: ZK search (high precision)
    Tier 2: Vector search (for unknown topics)

    Args:
        - query: str - Search query (required)
        - max_results: int - Maximum results (default: 10)
        - use_hybrid: bool - Use vector fallback (default: true)

    Returns:
        ZK results, vector results, and merged results.
    """,
    autowire=True,
)
async def zk_hybrid_search(
    query: str,
    max_results: int = 10,
    use_hybrid: bool = True,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Hybrid search with ZK + Vector fallback."""
    try:
        if paths is None:
            paths = ConfigPaths()

        # Create a simple vector fallback (can be replaced with real vector search)
        async def vector_fallback(q: str, limit: int = 10) -> list[dict]:
            # Placeholder: In production, this would query a vector DB
            return []

        searcher = ZkHybridSearcher(
            notebook_dir=str(paths.project_root),
            vector_search_func=vector_fallback,
        )

        result = await searcher.search(query, max_results=max_results, use_hybrid=use_hybrid)

        return {
            "success": True,
            "query": query,
            "zk_results": result["zk_results"],
            "zk_total": result["total_zk"],
            "vector_total": result["total_vector"],
            "merged": result["merged_results"][:max_results],
            "merged_total": result["total_merged"],
        }
    except Exception as e:
        logger.error(f"ZK hybrid search failed: {e}")
        raise


@skill_command(
    name="zk_stats",
    category="info",
    description="""
    Get knowledge base statistics from ZK notebook.

    Returns:
    - Total notes
    - Orphans (unlinked notes)
    - Graph statistics
    """,
    autowire=True,
)
async def zk_stats(
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Get ZK knowledge base statistics."""
    try:
        if paths is None:
            paths = ConfigPaths()

        from omni.rag.zk_integration import ZkClient

        client = ZkClient(str(paths.project_root))
        stats = await client.get_stats()

        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"ZK stats failed: {e}")
        raise


@skill_command(
    name="zk_links",
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
async def zk_links(
    note_id: str,
    direction: str = "both",
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Find notes linked to/from a specific note."""
    try:
        if paths is None:
            paths = ConfigPaths()

        from omni.rag.zk_integration import ZkClient

        client = ZkClient(str(paths.project_root))
        outgoing, incoming = await client.get_links(note_id, direction=direction)

        return {
            "success": True,
            "note_id": note_id,
            "direction": direction,
            "incoming": [
                {
                    "id": link["source"],
                    "title": link["sourceTitle"],
                    "type": link["type"],
                }
                for link in incoming
            ],
            "outgoing": [
                {
                    "id": link["target"],
                    "title": link["targetTitle"],
                    "type": link["type"],
                }
                for link in outgoing
            ],
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
        }
    except Exception as e:
        logger.error(f"ZK links failed: {e}")
        raise


@skill_command(
    name="zk_find_related",
    category="search",
    description="""
    Find notes related to a given note using ZK's --related flag.

    Args:
        - note_id: str - Starting note ID (required)
        - max_distance: int - Maximum link distance (default: 2)
        - limit: int - Maximum results (default: 20)

    Returns:
        List of related notes with distance information.
    """,
    autowire=True,
)
async def zk_find_related(
    note_id: str,
    max_distance: int = 2,
    limit: int = 20,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Find notes related to a given note."""
    try:
        if paths is None:
            paths = ConfigPaths()

        from omni.rag.zk_integration import ZkClient

        client = ZkClient(str(paths.project_root))
        related = await client.find_related(note_id, max_distance=max_distance, limit=limit)

        return {
            "success": True,
            "note_id": note_id,
            "max_distance": max_distance,
            "total": len(related),
            "results": [
                {
                    "id": n.filename_stem,
                    "title": n.title,
                    "path": n.path,
                }
                for n in related
            ],
        }
    except Exception as e:
        logger.error(f"ZK find_related failed: {e}")
        raise


__all__ = [
    "zk_search",
    "zk_toc",
    "zk_hybrid_search",
    "zk_stats",
    "zk_links",
    "zk_find_related",
]
