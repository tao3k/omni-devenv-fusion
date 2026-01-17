"""
agent/testing/plugin.py - Pytest Plugin for Skill Tests

Auto-discovers and registers skill fixtures for testing.

Usage:
    pytest_plugins = ["agent.testing.plugin"]

    def test_my_skill(git):  # 'git' fixture auto-injected
        result = git.smart_commit(action="start")
        assert result is not None
"""

import sys

from common.skills_path import SKILLS_DIR
from agent.testing.fixtures import _create_base_fixtures, _create_skill_fixture
from agent.testing.setup import _setup_agent_skills_core, _setup_skill_package_context


def pytest_configure(config):
    """
    Pytest hook: Auto-scan assets/skills and register skill fixtures.

    This runs once at pytest startup, registering all skills as fixtures.
    """
    skills_root = SKILLS_DIR()

    # Pre-load agent.skills.core for conftest compatibility
    # This ensures ModuleNotFoundError doesn't occur when tests import agent.skills.core
    try:
        import agent.skills.core
    except ImportError:
        # Fallback: manually set up the module if import fails
        _setup_agent_skills_core()

    # Pre-register all skill packages for direct imports
    # This enables `from agent.skills.git.scripts import status` in tests
    if skills_root.exists():
        for item in skills_root.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")):
                _setup_skill_package_context(item.name, skills_root)

    # Register base fixtures to the plugin module
    base_fixtures = _create_base_fixtures()
    for name, fixture in base_fixtures.items():
        setattr(sys.modules[__name__], name, fixture)

    if not skills_root.exists():
        return

    # Create and register fixtures for all valid skill directories
    for item in skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            fixture_name, fixture = _create_skill_fixture(item.name, skills_root)
            setattr(sys.modules[__name__], fixture_name, fixture)


# Re-export utilities for backward compatibility
from agent.testing.utils import get_skills, get_skill_module

__all__ = [
    "get_skills",
    "get_skill_module",
]
