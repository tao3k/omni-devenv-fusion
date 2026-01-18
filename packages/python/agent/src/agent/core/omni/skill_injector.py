"""
skill_injector.py - Skill Injection with Name Boosting and Hybrid Search.

Injects relevant skills based on task intent using Hybrid Discovery:
1. Name Boosting: Check if task explicitly mentions any known skill name
2. Semantic/Keyword Search: Use VectorStore's hybrid search for relevance
"""

from __future__ import annotations

import re
import structlog
from typing import Set

logger = structlog.get_logger(__name__)


class SkillInjector:
    """
    Skill Injector - Injects relevant skills based on task intent.

    Hybrid Discovery Mechanism:
    1. Name Boosting: Check if task explicitly mentions any known skill name
    2. Semantic/Keyword Search: Use VectorStore's hybrid search for relevance
    3. Load any unloaded relevant skills via JIT loader
    4. Update TTL for accessed skills
    """

    def __init__(self) -> None:
        self._last_task: str = ""

    async def inject_for_task(self, task: str) -> None:
        """
        Ensure skills relevant to the task are loaded.

        Args:
            task: The current task/query to analyze
        """
        from agent.core.skill_runtime import get_skill_context
        from agent.core.vector_store import get_vector_memory

        try:
            vm = get_vector_memory()
            if vm is None:
                logger.debug("SkillInjector: Vector memory not available, skipping skill injection")
                return

            manager = get_skill_context()
            relevant_skills: set[str] = set()

            # Step 1: Name Boosting (Data-Driven, not hardcoded)
            task_lower = task.lower()

            # Get all known skill names from the vector store index
            all_known_skills = set()
            try:
                # Try to get skill names from vector store (if method exists)
                if hasattr(vm, "get_all_skill_names"):
                    all_known_skills = vm.get_all_skill_names()
                else:
                    # Fallback: get from manager's loaded skills + core skills
                    all_known_skills = manager._skills.keys() | manager._core_skills
            except Exception:
                all_known_skills = manager._skills.keys() | manager._core_skills

            # Check for explicit skill name mentions with word boundary matching
            for skill_name in all_known_skills:
                # Use regex \b for word boundary to prevent false positives
                pattern = rf"\b{re.escape(skill_name)}\b"
                if re.search(pattern, task_lower):
                    logger.info(
                        "SkillInjector: Name Boost - detected explicit skill mention",
                        skill=skill_name,
                        task_preview=task[:50],
                    )
                    relevant_skills.add(skill_name)

            # Step 2: Hybrid Search (Vector + Keyword)
            search_results = await vm.search_tools_hybrid(
                query=task,
                limit=10,
            )

            if search_results:
                for result in search_results:
                    metadata = result.get("metadata", {})
                    skill_name = metadata.get("skill_name", "")
                    if skill_name:
                        relevant_skills.add(skill_name)

            if not relevant_skills:
                logger.debug("SkillInjector: No relevant skills found")
                return

            # Step 3: Load unloaded relevant skills
            loaded_count = 0
            for skill_name in relevant_skills:
                # Skip if already loaded
                if skill_name in manager._skills:
                    # Update TTL for already-loaded skills
                    manager._touch_skill(skill_name)
                    continue

                # Skip if core skill (should already be loaded)
                if skill_name in manager._core_skills:
                    continue

                # JIT load the skill
                try:
                    await manager._try_jit_load(skill_name)
                    loaded_count += 1
                    logger.info(
                        "SkillInjector: Intent-Driven Loading - loaded skill for task",
                        skill=skill_name,
                        task_preview=task[:50],
                    )
                except Exception as e:
                    logger.warning(
                        "SkillInjector: Failed to JIT load skill",
                        skill=skill_name,
                        error=str(e),
                    )

            if loaded_count > 0:
                logger.info(
                    "SkillInjector: Intent-Driven Loading complete",
                    loaded=loaded_count,
                    relevant=len(relevant_skills),
                )

            self._last_task = task

        except Exception as e:
            logger.warning(
                "SkillInjector: Intent-Driven Loading failed",
                error=str(e),
            )
            # Gracefully continue - skill injection is best-effort

    def get_injected_skills(self) -> Set[str]:
        """Get the set of skills injected for the last task."""
        # This could be enhanced to track actual loaded skills
        return set()


# Convenience function for singleton access
_skill_injector: SkillInjector | None = None


def get_skill_injector() -> SkillInjector:
    """Get the singleton SkillInjector instance."""
    global _skill_injector
    if _skill_injector is None:
        _skill_injector = SkillInjector()
    return _skill_injector


__all__ = ["SkillInjector", "get_skill_injector"]
