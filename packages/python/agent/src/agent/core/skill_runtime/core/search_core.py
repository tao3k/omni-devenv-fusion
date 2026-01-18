"""
search_core.py - Skill Semantic Search

Handles skill discovery using semantic search via vector store.
Used by Ghost Tool Injection to find relevant unloaded tools.
"""

from pathlib import Path
from typing import Any


class SkillSearchManager:
    """
    Manages semantic search for skills using vector store.

    Features:
    - Semantic skill search
    - Hybrid search (semantic + keyword)
    - Results transformation for tool injection
    """

    __slots__ = ()

    def __init__(self) -> None:
        """Initialize search manager (no external dependencies)."""

    async def search_skills(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for skills matching the query using semantic search.

        Used by Ghost Tool Injection to find relevant unloaded tools.

        Args:
            query: Natural language query describing the task
            limit: Maximum number of results to return

        Returns:
            List of matching skill dicts with id, name, description, score
        """
        from agent.core.vector_store import get_vector_memory

        try:
            vm = get_vector_memory()
            results = await vm.search_tools_hybrid(query, limit=limit)

            # Transform results to match expected format
            transformed: list[dict[str, Any]] = []
            for r in results:
                metadata = r.get("metadata", {})
                transformed.append(
                    {
                        "id": r.get("id", ""),
                        "name": metadata.get("skill_name", r.get("id", "").split(".")[0]),
                        "description": r.get("content", ""),
                        "score": 1.0 - r.get("distance", 1.0),
                        "metadata": metadata,
                    }
                )

            return transformed
        except Exception:
            return []

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Simple semantic search for skills.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching skills with scores
        """
        return await self.search_skills(query, limit)


__all__ = ["SkillSearchManager"]
