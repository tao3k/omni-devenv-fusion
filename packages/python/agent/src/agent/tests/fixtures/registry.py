"""
Registry Fixtures

Skill registry and manager fixtures for test isolation.
Loaded automatically as pytest plugins.

Fixtures:
    - registry_fixture: Clean SkillRegistry instance
    - isolated_registry: Registry with no pre-loaded skills
    - skill_manager_fixture: Clean SkillManager instance
    - skill_loader: Function to load skill modules
    - loaded_git_skill: Pre-loaded git skill module
    - loaded_filesystem_skill: Pre-loaded filesystem skill module
"""

import pytest
from pathlib import Path
from typing import Callable, Any

from common.skills_path import load_skill_module


@pytest.fixture
def fixtures_registry_registry_fixture():
    """Fixture to provide a clean SkillRegistry instance.

    Yields:
        A fresh registry with cleared cache
    """
    import agent.core.registry as sr_module

    # Reset singleton
    sr_module.SkillRegistry._instance = None

    reg = sr_module.get_skill_registry()
    reg.loaded_skills.clear()
    reg.module_cache.clear()

    yield reg

    # Cleanup
    reg.loaded_skills.clear()
    reg.module_cache.clear()


@pytest.fixture
def fixtures_registry_isolated_registry(fixtures_registry_registry_fixture):
    """Get an isolated registry with no pre-loaded skills.

    This is the preferred fixture for tests that need a clean state.
    """
    fixtures_registry_registry_fixture.loaded_skills.clear()
    fixtures_registry_registry_fixture.module_cache.clear()
    return fixtures_registry_registry_fixture


@pytest.fixture
def fixtures_registry_skill_manager_fixture():
    """Fixture to provide a clean SkillManager instance.

    Yields:
        A fresh skill manager with all skills loaded
    """
    import agent.core.skill_manager as sm_module

    # Reset singletons
    sm_module._skill_manager = None
    sm_module._manager = None

    manager = sm_module.get_skill_manager()
    # Load all skills for tests that need them
    manager.load_all()
    yield manager

    # Cleanup
    sm_module._skill_manager = None
    sm_module._manager = None


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
    fixtures_registry_registry_fixture.loaded_skills["git"] = module
    return module


@pytest.fixture
def fixtures_registry_loaded_filesystem_skill(fixtures_registry_registry_fixture):
    """Fixture that loads the filesystem skill and yields the module."""
    module = load_skill_module("filesystem")
    fixtures_registry_registry_fixture.loaded_skills["filesystem"] = module
    return module
