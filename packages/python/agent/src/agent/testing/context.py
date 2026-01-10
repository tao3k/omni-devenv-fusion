"""
agent/testing/context.py - Unified Skills Context for Type Hints

This module provides a centralized SkillsContext class that enables
IDE autocomplete for dynamically injected skill fixtures.

Usage:
    def test_workflow(skills):  # IDE infers SkillsContext
        skills.git.init()
        skills.docker.run()

Architecture:
    - TYPE_CHECKING imports for static type analysis
    - __getattr__ delegation to pytest fixtures at runtime
    - No runtime overhead when type hints aren't used
"""

from typing import TYPE_CHECKING, Any
import pytest

if TYPE_CHECKING:
    # Static imports only - no runtime dependency
    # These imports enable IDE autocomplete
    from assets.skills.git import tools as git_tools
    from assets.skills.knowledge import tools as knowledge_tools
    from assets.skills.filesystem import tools as filesystem_tools
    from assets.skills.skill import tools as skill_tools


class SkillsContext:
    """
    Virtual context class for type hints only.

    Runtime behavior:
        - Delegates to pytest fixtures via __getattr__
        - Lazy fixture resolution (only when accessed)

    Type hints:
        - All properties return typed references for IDE autocomplete
        - Actual fixture values returned at runtime

    Example:
        skills.git.init()  # Returns actual git fixture at runtime
                          # IDE knows git has init() method
    """

    def __init__(self, request: pytest.FixtureRequest):
        self._request = request
        # Cache accessed fixtures to avoid repeated lookups
        self._cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to pytest fixtures."""
        if name.startswith("_"):
            raise AttributeError(name)

        if name in self._cache:
            return self._cache[name]

        # Get fixture from pytest
        fixture = self._request.getfixturevalue(name)
        self._cache[name] = fixture
        return fixture

    def __dir__(self) -> list[str]:
        """List available skills for IDE autocomplete."""
        return ["git", "knowledge", "filesystem", "skill"]

    # Explicit type hints for IDE autocomplete
    # These are property stubs - actual values come from fixtures

    @property
    def git(self) -> "git_tools":
        """Git skill fixture."""
        return self._request.getfixturevalue("git")

    @property
    def knowledge(self) -> "knowledge_tools":
        """Knowledge skill fixture."""
        return self._request.getfixturevalue("knowledge")

    @property
    def filesystem(self) -> "filesystem_tools":
        """Filesystem skill fixture."""
        return self._request.getfixturevalue("filesystem")

    @property
    def skill(self) -> "skill_tools":
        """Skill skill fixture."""
        return self._request.getfixturevalue("skill")


def get_skills_context(request: pytest.FixtureRequest) -> SkillsContext:
    """
    Factory function to create SkillsContext.

    Args:
        request: Pytest FixtureRequest object

    Returns:
        SkillsContext instance with typed access to all skill fixtures
    """
    return SkillsContext(request)


# Export for plugin.py
__all__ = ["SkillsContext", "get_skills_context"]
