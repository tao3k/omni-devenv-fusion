"""
Pytest fixture registration for skill testing.

Registers base fixtures and skill-specific fixtures.
"""

from pathlib import Path

import pytest

from common.skills_path import SKILLS_DIR
from agent.testing.constants import PYTEST_BUILTIN_FIXTURES, RESERVED_FIXTURES
from agent.testing.proxy import SkillProxy
from agent.testing.setup import _setup_skill_package_context


def _create_base_fixtures():
    """Create base fixtures: skills_root, project_root, skills_dir.

    Returns a dict of fixtures to be registered by the plugin.
    """

    @pytest.fixture
    def skills_root_fixture() -> Path:
        """Skills root directory (assets/skills)."""
        return SKILLS_DIR()

    @pytest.fixture
    def project_root_fixture() -> Path:
        """Project root directory."""
        return SKILLS_DIR().parent

    @pytest.fixture
    def skills_dir_fixture() -> Path:
        """Alias for skills_root (for backward compatibility)."""
        return SKILLS_DIR()

    @pytest.fixture
    def skills_fixture(request: pytest.FixtureRequest) -> "SkillsContext":
        """
        Unified Skills Context for IDE type hints.

        Usage:
            def test_workflow(skills):  # IDE infers SkillsContext
                skills.git.init()
                skills.docker.run()
        """
        from agent.testing.context import SkillsContext

        return SkillsContext(request)

    return {
        "skills_root": skills_root_fixture,
        "project_root": project_root_fixture,
        "skills_dir": skills_dir_fixture,
        "skills": skills_fixture,
    }


def _create_skill_fixture(skill_name: str, skills_root: Path):
    """
    Create a fixture for a skill.

    Returns a tuple of (fixture_name, fixture_function).

    Collision Detection:
        - Checks against RESERVED_FIXTURES and PYTEST_BUILTIN_FIXTURES
        - Logs warning if skill name conflicts with pytest built-ins
        - Skills with conflicting names still get registered via skills.git
    """
    # Collision detection
    if skill_name in RESERVED_FIXTURES or skill_name in PYTEST_BUILTIN_FIXTURES:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Skill '{skill_name}' conflicts with pytest fixture. "
            f"Use 'skills.{skill_name}' instead of '{skill_name}' fixture."
        )

    @pytest.fixture(name=skill_name, scope="function")
    def _skill_fixture():
        """Dynamic fixture that loads skill via SkillManager.

        Returns a SkillProxy that exposes commands as direct methods.
        """
        scripts_path = skills_root / skill_name / "scripts"

        if not scripts_path.exists() or not any(scripts_path.glob("*.py")):
            pytest.skip(f"Skill '{skill_name}' has no scripts/*.py")

        # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
        _setup_skill_package_context(skill_name, skills_root)

        from agent.core.skill_runtime import get_skill_context

        manager = get_skill_context()
        skill = manager.skills.get(skill_name)
        if skill is None:
            pytest.skip(f"Skill '{skill_name}' failed to load")

        # Return a proxy that exposes commands as direct methods
        return SkillProxy(skill)

    return (skill_name, _skill_fixture)
