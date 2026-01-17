"""
src/agent/core/skill_discovery/indexing.py
 The Librarian - Vector-Based Skill Discovery

Semantic skill search using Rust-backed VectorMemory (LanceDB).
"""

from __future__ import annotations

from typing import Any

from common.skills_path import SKILLS_DIR

# Collection name for skill registry
SKILL_REGISTRY_COLLECTION = "skill_registry"


class SkillDiscovery:
    """
    Vector-based Semantic Skill Discovery.

    Uses VectorMemory (LanceDB) for semantic search over skill definitions.
    """

    def __init__(self) -> None:
        """Initialize the discovery adapter."""
        self._vm: Any = None

    def _get_vector_memory(self) -> Any:
        """Get VectorMemory instance lazily."""
        if self._vm is None:
            from agent.core.vector_store import get_vector_memory

            self._vm = get_vector_memory()
        return self._vm

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
        vm = self._get_vector_memory()
        skills_dir = SKILLS_DIR()
        stats = await vm.sync_skills(
            base_path=str(skills_dir),
            table_name="skills",
        )

        return {
            "success": True,
            "stats": stats,
            "local_skills_indexed": stats.get("total", 0),
        }

    async def search(
        self, query: str, limit: int = 5, local_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        Semantic search for skills/tools.

        Uses VectorMemory.search_tools_hybrid() which:
        - Performs vector similarity search (LanceDB ANN)
        - Applies keyword boosting for better relevance
        - Returns results sorted by hybrid score

        Args:
            query: Natural language query
            limit: Maximum results to return
            local_only: If True, only return installed skills

        Returns:
            List of matching tools with metadata
        """
        vm = self._get_vector_memory()
        results = await vm.search_tools_hybrid(query, limit=limit)

        # Transform to simplified format for SkillManager/Orchestrator
        formatted: list[dict[str, Any]] = []
        for r in results:
            metadata = r.get("metadata", {})
            distance = r.get("distance", 0.0)

            # Extract skill name - prefer metadata.name, fall back to id parsing
            raw_id = r.get("id", "")
            if metadata.get("name"):
                skill_name = metadata.get("name")
            elif raw_id.startswith("skill-"):
                skill_name = raw_id[6:]  # Strip "skill-" prefix
            else:
                skill_name = raw_id.split(".")[0]

            # Calculate keyword matches based on query presence in content/keywords
            keywords_str = metadata.get("keywords", "")
            keywords_list = [k.strip() for k in keywords_str.split(",")]
            query_lower = query.lower()
            keyword_matches = sum(1 for k in keywords_list if k.lower() in query_lower)
            keyword_bonus = keyword_matches * 0.1  # 10% bonus per keyword match

            # Convert installed string to boolean
            installed_raw = metadata.get("installed", "true")
            installed_bool = (
                installed_raw.lower() in ("true", "1", "yes")
                if isinstance(installed_raw, str)
                else bool(installed_raw)
            )

            # Skip uninstalled skills if local_only=True
            if local_only and not installed_bool:
                continue

            formatted.append(
                {
                    "id": skill_name,
                    "name": metadata.get("skill_name", skill_name),
                    "description": r.get("content", ""),
                    "score": 1.0 - distance,
                    "raw_vector_score": 1.0 - distance,
                    "calibrated_vector": 1.0 - distance,
                    "keyword_matches": keyword_matches,
                    "keyword_bonus": keyword_bonus,
                    "installed": installed_bool,
                    "keywords": metadata.get("keywords", ""),
                    "metadata": metadata,
                }
            )

        return formatted

    async def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the skill index."""
        vm = self._get_vector_memory()
        count = await vm.count(collection=SKILL_REGISTRY_COLLECTION)
        collections = await vm.list_collections()
        return {
            "collection": SKILL_REGISTRY_COLLECTION,
            "skill_count": count,
            "available_collections": collections,
        }


# =============================================================================
# Convenience functions for direct imports
# =============================================================================


async def reindex_skills_from_manifests() -> dict[str, Any]:
    """Convenience function to reindex all skills."""
    discovery = SkillDiscovery()
    return await discovery.reindex_all()


async def search_skills(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Convenience function to search skills semantically."""
    discovery = SkillDiscovery()
    return await discovery.search(query, limit)


__all__ = [
    "SkillDiscovery",
    "reindex_skills_from_manifests",
    "search_skills",
    "SKILL_REGISTRY_COLLECTION",
]
