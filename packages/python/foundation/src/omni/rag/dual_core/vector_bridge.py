"""Bridge 2: LanceDB → ZK Hybrid Search (vector fallback).

Builds a LanceDB-backed async search function compatible with ZkHybridSearcher.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("omni.rag.dual_core")


def build_vector_search_for_zk(
    collection: str = "knowledge_chunks",
) -> Any:
    """Build a LanceDB-backed async search function for ZkHybridSearcher.

    Returns an async callable: (query: str, limit: int) -> list[dict]
    """

    async def _vector_search(query: str, limit: int = 10) -> list[dict]:
        """Execute LanceDB vector search, returning ZK-compatible result dicts."""
        try:
            from omni.rag.retrieval.lancedb import LanceRetrievalBackend
            from omni.rag.retrieval.interface import RetrievalConfig

            backend = LanceRetrievalBackend()
            config = RetrievalConfig(
                top_k=limit,
                collection=collection,
                score_threshold=0.0,
            )
            retrieval_results = await backend.search(query, config)

            return [
                {
                    "id": r.id,
                    "filename_stem": Path(r.id).stem if r.id else "",
                    "score": r.score,
                    "content": r.content[:200] if r.content else "",
                    "note": None,
                    "source": "vector",
                }
                for r in retrieval_results
            ]
        except Exception as e:
            logger.debug("LanceDB vector search failed: %s", e)
            return []

    return _vector_search


async def get_dual_core_searcher(
    project_root: str | Path | None = None,
    collection: str = "knowledge_chunks",
) -> Any:
    """Create a ZkHybridSearcher with both cores connected.

    Args:
        project_root: Project root where .zk/ lives.
        collection: LanceDB collection for vector search.

    Returns:
        ZkHybridSearcher with both cores connected.
    """
    from omni.rag.zk_search import ZkHybridSearcher, ZkSearchConfig

    root = Path(project_root) if project_root else Path.cwd()
    vector_fn = build_vector_search_for_zk(collection)

    return ZkHybridSearcher(
        notebook_dir=str(root),
        zk_config=ZkSearchConfig(
            max_iterations=3,
            max_notes_per_iteration=10,
            use_vector_fallback=True,
        ),
        vector_search_func=vector_fn,
    )
