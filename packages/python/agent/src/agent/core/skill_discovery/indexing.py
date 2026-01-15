"""
src/agent/core/skill_discovery/indexing.py
Phase 66: The Librarian - Adapter for VectorMemory.

This module is a lightweight adapter that connects SkillManager to the
Rust-backed VectorMemory (LanceDB) for semantic skill discovery.

No file scanning or indexing logic here - all delegated to VectorMemory.
"""

from __future__ import annotations

from typing import Any

from common.skills_path import SKILLS_DIR

# Backward compatibility constant for old ChromaDB-based vector.py
SKILL_REGISTRY_COLLECTION = "skill_registry"


class SkillDiscovery:
    """
    The Librarian: Facade for Semantic Skill Search.

    Acts as a lightweight adapter between SkillManager and VectorMemory.
    All heavy lifting (scanning, indexing, searching) is done by VectorMemory.
    """

    def __init__(self) -> None:
        """Initialize the discovery adapter."""
        from agent.core.vector_store import get_vector_memory

        self.vm = get_vector_memory()
        self.skills_dir = SKILLS_DIR()

    async def reindex_all(self, skill_manager: Any | None = None) -> dict[str, Any]:
        """
        Trigger a full incremental sync of skills to the vector DB.

        Uses VectorMemory.sync_skills() which:
        - Scans skills using Rust ScriptScanner
        - Computes file hashes for incremental updates
        - Only updates changed files

        Args:
            skill_manager: Optional reference (unused, kept for interface compat)

        Returns:
            Dict with sync stats: added, modified, deleted, total
        """
        stats = await self.vm.sync_skills(
            base_path=str(self.skills_dir),
            table_name="skills",
        )

        return {
            "success": True,
            "stats": stats,
            "local_skills_indexed": stats.get("total", 0),
            "remote_skills_indexed": 0,  # No remote skills for local discovery
        }

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Semantic search for skills/tools.

        Uses VectorMemory.search_tools_hybrid() which:
        - Performs vector similarity search (LanceDB ANN)
        - Applies keyword boosting for better relevance
        - Returns results sorted by hybrid score

        Args:
            query: Natural language query
            limit: Maximum results to return

        Returns:
            List of matching tools with metadata
        """
        results = await self.vm.search_tools_hybrid(query, limit=limit)

        # Transform to simplified format for SkillManager/Orchestrator
        formatted: list[dict[str, Any]] = []
        for r in results:
            metadata = r.get("metadata", {})
            formatted.append(
                {
                    "id": r.get("id", ""),  # e.g., "git.commit"
                    "name": metadata.get("skill_name", r.get("id", "").split(".")[0]),
                    "description": r.get("content", ""),
                    "score": 1.0 - r.get("distance", 1.0),  # Convert distance to similarity
                    "metadata": metadata,
                }
            )

        return formatted


# =============================================================================
# Convenience functions for direct imports
# =============================================================================


async def reindex_skills_from_manifests() -> dict[str, Any]:
    """
    Convenience function to reindex all skills.

    Uses VectorMemory.sync_skills() for efficient incremental updates.

    Returns:
        Dict with sync stats
    """
    discovery = SkillDiscovery()
    return await discovery.reindex_all()


async def vector_search_skills(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Convenience function to search skills semantically.

    Uses VectorMemory.search_tools_hybrid() for hybrid search.

    Args:
        query: Search query
        limit: Max results

    Returns:
        List of matching skills
    """
    discovery = SkillDiscovery()
    return await discovery.search(query, limit)


__all__ = [
    "SkillDiscovery",
    "reindex_skills_from_manifests",
    "vector_search_skills",
    "SKILL_REGISTRY_COLLECTION",
]
