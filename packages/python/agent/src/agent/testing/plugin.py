"""
agent/testing/plugin.py - Pytest Plugin for Skill Tests

Phase 35.1: First-class Pytest plugin that automatically discovers
and registers skill fixtures.

Inspired by Prefect's test harness pattern - no conftest.py needed!

Usage:
    pytest_plugins = ["agent.testing.plugin"]

    def test_my_skill(git):  # 'git' fixture auto-injected
        assert git.status().success

    def test_integration(my_skill, git):  # Multiple skills work too
        my_skill.sync()
        assert git.status()
"""

import pytest
import sys
import importlib.util
from pathlib import Path
from common.skills_path import SKILLS_DIR


def pytest_configure(config):
    """
    Pytest hook: Auto-scan assets/skills and register skill fixtures.

    This runs once at pytest startup, registering all skills as fixtures.
    """
    skills_root = SKILLS_DIR()

    # Register base fixtures first
    _register_base_fixtures(skills_root)

    if not skills_root.exists():
        return

    # Scan all valid skill directories and register fixtures
    for item in skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            _register_skill_fixture(item.name, skills_root)


def _register_base_fixtures(skills_root: Path):
    """Register base fixtures: skills_root, project_root, skills_dir."""

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

    # Register them globally
    setattr(sys.modules[__name__], "skills_root", skills_root_fixture)
    setattr(sys.modules[__name__], "project_root", project_root_fixture)
    setattr(sys.modules[__name__], "skills_dir", skills_dir_fixture)


def _register_skill_fixture(skill_name: str, skills_root: Path):
    """Dynamically create and register a fixture for a skill."""

    @pytest.fixture(name=skill_name, scope="function")
    def _skill_fixture():
        """Dynamic fixture that loads skill/tools.py on demand."""
        tools_path = skills_root / skill_name / "tools.py"
        if not tools_path.exists():
            pytest.skip(f"Skill '{skill_name}' missing tools.py")

        module_name = f"_skill_{skill_name}_module"
        spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
        if spec is None or spec.loader is None:
            pytest.skip(f"Skill '{skill_name}' cannot be loaded")

        # Check if already loaded
        if module_name in sys.modules:
            return sys.modules[module_name]

        # Load and cache
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    # Black magic: Register fixture globally so pytest can find it
    # This makes `def test_xxx(git):` work without any imports
    setattr(sys.modules[__name__], skill_name, _skill_fixture)


# =============================================================================
# Utility Functions (for advanced users)
# =============================================================================


def get_skills() -> list[str]:
    """List all available skills."""
    skills_root = SKILLS_DIR()
    if not skills_root.exists():
        return []
    return [
        item.name
        for item in skills_root.iterdir()
        if item.is_dir() and not item.name.startswith(("_", "."))
    ]


def get_skill_module(skill_name: str):
    """Get a skill module directly (without fixture)."""
    skills_root = SKILLS_DIR()
    tools_path = skills_root / skill_name / "tools.py"
    if not tools_path.exists():
        return None

    module_name = f"_skill_{skill_name}_module"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Export for convenience
__all__ = [
    "get_skills",
    "get_skill_module",
]
