"""
Registry Fixtures

Skill registry and manager fixtures for test isolation.
Loaded automatically as pytest plugins.

Fixtures:
    - registry_fixture: Clean SkillRegistry instance
    - isolated_registry: Registry with no pre-loaded skills
    - skill_manager_fixture: Clean SkillContext instance
    - skill_loader: Function to load skill modules
    - loaded_git_skill: Pre-loaded git skill module
    - loaded_filesystem_skill: Pre-loaded filesystem skill module
"""

from collections.abc import Callable
from typing import Any

import pytest

from omni.foundation.config.skills import load_skill_module


@pytest.fixture
def fixtures_registry_registry_fixture():
    """Fixture to provide a clean SkillRegistry instance.

    Yields:
        A fresh registry with cleared cache
    """
    from omni.core.skills.registry import SkillRegistry, get_skill_registry

    # Reset singleton
    SkillRegistry._instance = None

    reg = get_skill_registry()
    # In thin client mode, _skills dict may be empty
    reg._skills.clear()

    yield reg

    # Cleanup
    reg._skills.clear()


@pytest.fixture
def fixtures_registry_isolated_registry(fixtures_registry_registry_fixture):
    """Get an isolated registry with no pre-loaded skills.

    This is the preferred fixture for tests that need a clean state.
    """
    fixtures_registry_registry_fixture._skills.clear()
    return fixtures_registry_registry_fixture


@pytest.fixture
def fixtures_registry_skill_manager_fixture():
    """Fixture to provide a clean SkillContext instance.

    Yields:
        A fresh skill manager (in thin client mode, may be minimal)
    """
    from omni.core.skills.runtime import SkillContext, reset_context

    # Reset singletons
    reset_context()

    yield SkillContext()


@pytest.fixture
def fixtures_registry_skill_loader() -> Callable[[str], Any]:
    """Provide a function to load skill modules in tests."""

    def _loader(skill_name: str):
        return load_skill_module(skill_name)

    return _loader


@pytest.fixture
def fixtures_registry_loaded_git_skill(fixtures_registry_registry_fixture):
    """Fixture that loads the git skill and yields the module."""
    module = load_skill_module("git")
    fixtures_registry_registry_fixture._skills["git"] = module
    return module


@pytest.fixture
def fixtures_registry_loaded_filesystem_skill(fixtures_registry_registry_fixture):
    """Fixture that loads the filesystem skill and yields the module."""
    module = load_skill_module("filesystem")
    fixtures_registry_registry_fixture._skills["filesystem"] = module
    return module
