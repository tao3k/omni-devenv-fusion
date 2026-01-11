"""
src/agent/core/skill_discovery/vector.py
Phase 36: Vector-Enhanced Skill Discovery (ChromaDB)

Semantic Skill Discovery using ChromaDB for intelligent matching.
"""

from __future__ import annotations

from typing import Any

import structlog

from .indexing import SKILL_REGISTRY_COLLECTION

logger = structlog.get_logger(__name__)


class VectorSkillDiscovery:
    """
    Semantic Skill Discovery using ChromaDB.

    Provides vector-based semantic search over skill definitions,
    enabling fuzzy matching even when exact keywords don't match.

    Features:
    - Semantic similarity search (e.g., "draw chart" → "visualization")
    - Hybrid search: vector + keyword fallback
    - Persistent index across sessions
    - Incremental updates for new skills
    """

    COLLECTION_NAME = SKILL_REGISTRY_COLLECTION

    def __init__(self):
        """Initialize vector-based skill discovery."""
        self._vm: Any = None

    def _get_vector_memory(self) -> Any:
        """Get VectorMemory instance lazily."""
        if self._vm is None:
            from agent.core.vector_store import get_vector_memory

            self._vm = get_vector_memory()
        return self._vm

    async def search(
        self, query: str, limit: int = 5, installed_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Search skills using semantic similarity.

        By default, only returns installed (local) skills.
        Set installed_only=False to search remote skills from known_skills.json.

        Args:
            query: Search query (natural language)
            limit: Maximum number of results
            installed_only: Only return installed (local) skills (default: True)

        Returns:
            List of matching skill dicts with metadata and scores
        """
        from typing import Dict, Optional

        vm = self._get_vector_memory()

        # Build filter for installed skills
        where_filter: Optional[Dict[str, str]] = None
        if installed_only:
            where_filter = {"installed": "true"}

        try:
            results = await vm.search(
                query=query,
                n_results=limit * 2,  # Get more to filter
                collection=self.COLLECTION_NAME,
                where_filter=where_filter,
            )

            # Convert SearchResult to skill dict format
            skills = []
            for res in results[:limit]:
                skills.append(
                    {
                        "id": res.metadata.get("id", res.id),
                        "name": res.metadata.get("name", res.metadata.get("id", "")),
                        "description": res.content[:200] if res.content else "",
                        "keywords": res.metadata.get("keywords", "").split(","),
                        "score": 1.0 - res.distance,  # Convert distance to similarity
                        "installed": res.metadata.get("installed", "false") == "true",
                        "type": res.metadata.get("type", "local"),
                    }
                )

            logger.info(
                "Vector skill search completed",
                query=query[:50],
                results=len(skills),
                method="semantic_vector",
            )
            return skills

        except Exception as e:
            logger.error("Vector skill search failed", error=str(e))
            return []

    async def suggest_for_query(self, query: str, limit: int = 5) -> dict[str, Any]:
        """
        Analyze a query and suggest skills using semantic search.

        Args:
            query: User's request/query
            limit: Maximum suggestions

        Returns:
            Dict with suggestions, method, and reasoning
        """
        suggestions = await self.search(query, limit=limit)

        return {
            "query": query,
            "suggestions": suggestions,
            "count": len(suggestions),
            "method": "semantic_vector",
            "ready_to_install": [s["id"] for s in suggestions if not s.get("installed", True)],
        }

    async def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the skill index."""
        vm = self._get_vector_memory()
        count = await vm.count(collection=self.COLLECTION_NAME)
        collections = await vm.list_collections()

        return {
            "collection": self.COLLECTION_NAME,
            "skill_count": count,
            "available_collections": collections,
        }


# Convenience functions
async def vector_search_skills(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Quick semantic search for skills.

    Args:
        query: Search query
        limit: Max results

    Returns:
        List of matching skills with scores
    """
    discovery = VectorSkillDiscovery()
    return await discovery.search(query, limit=limit)


async def vector_suggest_for_task(task: str) -> dict[str, Any]:
    """
    Get semantic skill suggestions for a task.

    Args:
        task: Task description

    Returns:
        Suggestion dict with matching skills
    """
    discovery = VectorSkillDiscovery()
    return await discovery.suggest_for_query(task)


__all__ = [
    "VectorSkillDiscovery",
    "vector_search_skills",
    "vector_suggest_for_task",
]
