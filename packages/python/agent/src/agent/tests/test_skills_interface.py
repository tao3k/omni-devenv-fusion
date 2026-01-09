"""
agent/tests/test_skills_interface.py - Atomic Test Interface for Skills

Phase 35.1: Single entry point for testing all skill interfaces.

This file uses the plugin pattern to enable seamless testing of all skills
without any additional configuration.

Usage:
    # Run all skill tests
    uv run pytest packages/python/agent/src/agent/tests/test_skills_interface.py -v

    # Or run directly from assets/skills
    uv run pytest assets/skills/ -v

No conftest.py needed - fixtures auto-registered by pyproject.toml!
"""

import pytest
from pathlib import Path
from common.skills_path import SKILLS_DIR


def test_skills_directory_exists():
    """Verify assets/skills directory exists."""
    skills_root = SKILLS_DIR()
    assert skills_root.exists(), f"Skills directory not found: {skills_root}"


def test_skills_have_tools():
    """Verify each skill has a tools.py file."""
    skills_root = SKILLS_DIR()
    if not skills_root.exists():
        pytest.skip("No skills directory")

    for item in skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            tools_path = item / "tools.py"
            assert tools_path.exists(), f"Skill '{item.name}' missing tools.py"


def test_skills_tests_discoverable():
    """Verify skills with tests can be discovered."""
    skills_root = SKILLS_DIR()
    if not skills_root.exists():
        pytest.skip("No skills directory")

    skills_with_tests = []
    for item in skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            tests_dir = item / "tests"
            if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
                skills_with_tests.append(item.name)

    assert len(skills_with_tests) > 0, "No skills with tests found"
    print(f"\n📦 Skills with tests: {', '.join(skills_with_tests)}")


# Export plugin for other test modules
__all__ = ["pytest_plugins"]
