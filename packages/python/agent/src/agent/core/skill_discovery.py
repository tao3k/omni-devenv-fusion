"""
src/agent/core/skill_discovery.py
Phase 27: JIT Skill Acquisition - Skill Discovery Protocol

Features:
- Search local skills index (known_skills.json)
- Fuzzy matching on keywords and description
- GitHub API fallback for discovery
- Auto-suggestion for missing capabilities
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import structlog

from common.skills_path import SKILLS_DIR

logger = structlog.get_logger(__name__)

# Default index path - read from settings.yaml via SKILLS_DIR
# Location: {assets.skills_dir}/skill/data/known_skills.json
KNOWN_SKILLS_INDEX = SKILLS_DIR(skill="skill", path="data/known_skills.json")


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
