"""
src/agent/core/skill_discovery.py
Phase 27: JIT Skill Acquisition - Skill Discovery Protocol
Phase 36: Vector-Enhanced Discovery (ChromaDB)

Features:
- Search local skills index (known_skills.json) - Legacy
- Vector-based semantic search (skill_registry collection) - Phase 36
- Fuzzy matching on keywords and description
- GitHub API fallback for discovery
- Auto-suggestion for missing capabilities
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from common.skills_path import SKILLS_DIR

logger = structlog.get_logger(__name__)

# Default index path - read from settings.yaml via SKILLS_DIR
# Location: {assets.skills_dir}/skill/data/known_skills.json
KNOWN_SKILLS_INDEX = SKILLS_DIR(skill="skill", path="data/known_skills.json")

# ChromaDB collection name for skill registry
SKILL_REGISTRY_COLLECTION = "skill_registry"


class SkillDiscovery:
    """
    Discover and suggest skills based on user queries or missing capabilities.

    Uses a local index (known_skills.json) with GitHub API fallback.
    """

    def __init__(self, index_path: Optional[Path] = None):
        """
        Initialize skill discovery.

        Args:
            index_path: Path to known_skills.json (default: data/known_skills.json)
        """
        self.index_path = index_path or KNOWN_SKILLS_INDEX
        self._index_cache: Optional[dict] = None

    def _load_index(self) -> dict:
        """Load the skills index from disk."""
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_path.exists():
            logger.warning(f"Skills index not found: {self.index_path}")
            return {"version": "1.0.0", "skills": []}

        try:
            data = json.loads(self.index_path.read_text())
            self._index_cache = data
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid skills index: {e}")
            return {"version": "1.0.0", "skills": []}

    def search_local(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search the local skills index for matching skills.

        Args:
            query: Search query (matched against name, description, keywords)
            limit: Maximum number of results to return

        Returns:
            List of matching skill metadata dicts
        """
        index = self._load_index()
        skills = index.get("skills", [])

        if not query:
            return skills[:limit]

        query_lower = query.lower()
        query_terms = set(re.findall(r"\w+", query_lower))

        def score_skill(skill: dict) -> tuple[int, float]:
            """Score a skill based on query relevance."""
            name = skill.get("name", "").lower()
            desc = skill.get("description", "").lower()
            keywords = [k.lower() for k in skill.get("keywords", [])]
            skill_id = skill.get("id", "").lower()

            score = 0

            # Exact keyword match (highest)
            for term in query_terms:
                if term in keywords:
                    score += 10
                if term in skill_id:
                    score += 8
                if term in name:
                    score += 5
                if term in desc:
                    score += 2

            # Partial match in name
            if query_lower in name:
                score += 3

            # Description contains query
            if query_lower in desc:
                score += 1

            return (score, 0)

        # Sort by score descending
        scored = [(score_skill(s), s) for s in skills]
        scored = [(s[0], s[1]) for s in scored if s[0][0] > 0]
        scored.sort(key=lambda x: (-x[0][0], x[0][1]))

        return [s[1] for s in scored[:limit]]

    def find_by_keyword(self, keyword: str) -> list[dict]:
        """
        Find skills that have a specific keyword.

        Args:
            keyword: Keyword to search for

        Returns:
            List of matching skills
        """
        keyword_lower = keyword.lower()
        index = self._load_index()
        skills = index.get("skills", [])

        return [s for s in skills if keyword_lower in [k.lower() for k in s.get("keywords", [])]]

    def find_by_id(self, skill_id: str) -> Optional[dict]:
        """
        Find a skill by its ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill metadata or None if not found
        """
        index = self._load_index()
        skills = index.get("skills", [])

        for skill in skills:
            if skill.get("id") == skill_id or skill.get("id").replace("-", "_") == skill_id:
                return skill

        return None

    def suggest_for_query(self, query: str) -> dict:
        """
        Analyze a query and suggest skills that could help.

        Args:
            query: User's request/query

        Returns:
            Dict with suggestions and reasoning
        """
        local_matches = self.search_local(query, limit=3)

        return {
            "query": query,
            "suggestions": local_matches,
            "count": len(local_matches),
            "ready_to_install": [s["id"] for s in local_matches],
        }

    def list_all(self) -> list[dict]:
        """
        List all known skills in the index.

        Returns:
            List of all skill metadata
        """
        index = self._load_index()
        return index.get("skills", [])

    def get_installation_info(self, skill_id: str) -> Optional[dict]:
        """
        Get installation information for a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            Dict with installation details or None
        """
        skill = self.find_by_id(skill_id)
        if not skill:
            return None

        return {
            "id": skill["id"],
            "name": skill["name"],
            "url": skill["url"],
            "description": skill["description"],
            "version": skill.get("version", "main"),
            "install_command": f"omni skill install {skill['url']}",
        }


# Convenience function
def discover_skills(query: str = "", limit: int = 5) -> list[dict]:
    """
    Quick search for skills.

    Args:
        query: Search query (optional)
        limit: Max results

    Returns:
        List of matching skills
    """
    discovery = SkillDiscovery()
    return discovery.search_local(query, limit)


def suggest_for_task(task: str) -> dict:
    """
    Get skill suggestions for a task.

    Args:
        task: Task description

    Returns:
        Suggestion dict with matching skills
    """
    discovery = SkillDiscovery()
    return discovery.suggest_for_query(task)


# =============================================================================
# Phase 36: Vector-Enhanced Skill Discovery
# =============================================================================


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
        self._vm: Optional[Any] = None

    def _get_vector_memory(self) -> Any:
        """Get VectorMemory instance lazily."""
        if self._vm is None:
            from agent.core.vector_store import get_vector_memory

            self._vm = get_vector_memory()
        return self._vm

    async def search(
        self, query: str, limit: int = 5, installed_only: bool = True
    ) -> List[Dict[str, Any]]:
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

    async def suggest_for_query(self, query: str, limit: int = 5) -> Dict[str, Any]:
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

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the skill index."""
        vm = self._get_vector_memory()
        count = await vm.count(collection=self.COLLECTION_NAME)
        collections = await vm.list_collections()

        return {
            "collection": self.COLLECTION_NAME,
            "skill_count": count,
            "available_collections": collections,
        }


# =============================================================================
# Skill Index Management (Phase 36)
# =============================================================================


async def reindex_skills_from_manifests(
    clear_existing: bool = True,
) -> Dict[str, Any]:
    """
    Reindex all installed skills into the vector store.

    Scans SKILL.md files from all installed skills and creates
    semantic embeddings for intelligent discovery.

    Args:
        clear_existing: Clear existing index before reindexing

    Returns:
        Dict with stats about the reindexing operation
    """
    from agent.core.registry import get_skill_registry
    from agent.core.vector_store import get_vector_memory

    registry = get_skill_registry()
    vm = get_vector_memory()

    # Get all installed skills
    skills = registry.list_available_skills()
    indexed = 0
    errors = []

    # Clear existing index if requested
    if clear_existing:
        try:
            client = vm.client
            if client:
                # Get the collection and delete it
                try:
                    collection = client.get_collection(name="skill_registry")
                    collection.delete()
                    logger.info("Cleared existing skill registry collection")
                except Exception:
                    # Collection might not exist yet
                    pass
        except Exception as e:
            logger.warning("Failed to clear existing collection", error=str(e))

    # Index each skill
    for skill_name in skills:
        try:
            manifest = registry.get_skill_manifest(skill_name)
            if not manifest:
                continue

            # Build rich semantic document from manifest
            semantic_text = _build_skill_document(manifest)

            success = await vm.add(
                documents=[semantic_text],
                ids=[f"skill-{skill_name}"],
                collection=SKILL_REGISTRY_COLLECTION,
                metadatas=[
                    {
                        "id": skill_name,
                        "name": skill_name,
                        "keywords": ",".join(manifest.routing_keywords),
                        "installed": "true",
                        "type": "local",
                        "version": manifest.version,
                    }
                ],
            )

            if success:
                indexed += 1
                logger.debug(f"Indexed skill: {skill_name}")

        except Exception as e:
            errors.append({"skill": skill_name, "error": str(e)})
            logger.error(f"Failed to index skill {skill_name}", error=str(e))

    # Also index remote skills from known_skills.json
    remote_indexed = await _index_remote_skills(vm)

    result = {
        "local_skills_indexed": indexed,
        "remote_skills_indexed": remote_indexed,
        "total_skills_indexed": indexed + remote_indexed,
        "errors": errors,
    }

    logger.info("Skill reindex completed", **result)
    return result


def _build_skill_document(manifest: Any) -> str:
    """
    Build a rich semantic document from a skill manifest.

    Combines description, keywords, and intents into a single
    text that will be embedded for semantic search.
    """
    parts = [
        f"Skill: {manifest.name}",
        f"Description: {manifest.description}",
    ]

    if manifest.routing_keywords:
        parts.append(f"Keywords: {', '.join(manifest.routing_keywords)}")

    if manifest.intents:
        parts.append(f"Intents: {', '.join(manifest.intents)}")

    if manifest.author:
        parts.append(f"Author: {manifest.author}")

    return "\n".join(parts)


async def _index_remote_skills(vm: Any) -> int:
    """
    Index remote skills from known_skills.json into the vector store.

    Args:
        vm: VectorMemory instance

    Returns:
        Number of remote skills indexed
    """
    index = SkillDiscovery()._load_index()
    skills = index.get("skills", [])

    indexed = 0
    for skill in skills:
        try:
            skill_id = skill.get("id", "")
            if not skill_id:
                continue

            # Build semantic document
            doc_parts = [
                f"Skill: {skill.get('name', skill_id)}",
                f"Description: {skill.get('description', '')}",
                f"Keywords: {', '.join(skill.get('keywords', []))}",
            ]

            if skill.get("repository"):
                repo = skill.get("repository")
                doc_parts.append(f"Repository: {repo.get('url', '')}")

            await vm.add(
                documents=["\n".join(doc_parts)],
                ids=[f"skill-remote-{skill_id}"],
                collection=SKILL_REGISTRY_COLLECTION,
                metadatas=[
                    {
                        "id": skill_id,
                        "name": skill.get("name", skill_id),
                        "keywords": ",".join(skill.get("keywords", [])),
                        "installed": "false",
                        "type": "remote",
                        "url": skill.get("url", ""),
                    }
                ],
            )
            indexed += 1

        except Exception as e:
            logger.warning(f"Failed to index remote skill {skill.get('id', '?')}", error=str(e))

    return indexed


# Convenience functions
async def vector_search_skills(query: str, limit: int = 5) -> List[Dict[str, Any]]:
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


async def vector_suggest_for_task(task: str) -> Dict[str, Any]:
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
    "SkillDiscovery",
    "VectorSkillDiscovery",
    "reindex_skills_from_manifests",
    "vector_search_skills",
    "vector_suggest_for_task",
    "SKILL_REGISTRY_COLLECTION",
]
