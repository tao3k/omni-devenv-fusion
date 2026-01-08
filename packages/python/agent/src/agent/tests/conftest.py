"""
Pytest Configuration and Common Fixtures for Omni-Dev Fusion Test Suite.

This module provides centralized pytest configuration and shared fixtures
to eliminate code duplication across test files.

Usage:
    pytest will automatically discover and load this conftest.py
    Fixtures defined here are available to all tests in this directory.

Example:
    async def test_something(isolated_registry, skill_loader):
        ...

Categories:
    - Path Fixtures: project_root, skills_path, temp_dir
    - Registry Fixtures: registry_fixture, isolated_registry, skill_loader
    - Manager Fixtures: skill_manager_fixture
    - Mock Fixtures: mock_mcp_server, mock_inference
    - Cleanup Fixtures: cleanup_threads, reset_singletons
    - Assertion Helpers: assert_match
"""

import pytest
import asyncio
import os
import importlib.util
from pathlib import Path
from typing import Generator, Any, Callable, Optional


from unittest.mock import MagicMock, AsyncMock


# Use common.skills_path for skills directory (replaces common.lib pattern)
from common.skills_path import SKILLS_DIR, load_skill_module
from common.gitops import get_project_root

_PROJECT_ROOT = get_project_root()


# =============================================================================
# Session-Scoped Paths (Computed Once)
# =============================================================================


@pytest.fixture(scope="session")
def project_paths() -> dict:
    """Session-scoped paths - computed once per test session."""
    return {
        "root": _PROJECT_ROOT,
        "skills": SKILLS_DIR(),  # From settings.yaml -> assets.skills_dir
    }


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return _PROJECT_ROOT


@pytest.fixture
def skills_path(project_paths) -> Path:
    """Return the skills directory path."""
    return project_paths["skills"]


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for tests."""
    return tmp_path


# =============================================================================
# Skill Loading Utilities (Using common.skills_path)
# =============================================================================

# load_skill_module is now imported from common.skills_path
# It handles path resolution and module loading automatically

# =============================================================================
# Registry Fixtures
# =============================================================================


@pytest.fixture
def skills_base_path(skills_path) -> Path:
    """Return the base path for skills directory (alias for compatibility)."""
    return skills_path


@pytest.fixture
def registry_fixture():
    """
    Fixture to provide a clean SkillRegistry instance.

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
def isolated_registry(registry_fixture):
    """
    Get an isolated registry with no pre-loaded skills.

    This is the preferred fixture for tests that need a clean state.
    """
    registry_fixture.loaded_skills.clear()
    registry_fixture.module_cache.clear()
    return registry_fixture


# =============================================================================
# Skill Manager Fixtures
# =============================================================================


@pytest.fixture
def skill_manager_fixture():
    """
    Fixture to provide a clean SkillManager instance.

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


# =============================================================================
# Pre-loaded Skill Fixtures
# =============================================================================


@pytest.fixture
def loaded_git_skill(registry_fixture):
    """Fixture that loads the git skill and yields the module."""
    module = load_skill_module("git")
    registry_fixture.loaded_skills["git"] = module
    return module


@pytest.fixture
def loaded_filesystem_skill(registry_fixture):
    """Fixture that loads the filesystem skill and yields the module."""
    module = load_skill_module("filesystem")
    registry_fixture.loaded_skills["filesystem"] = module
    return module


@pytest.fixture
def skill_loader() -> Callable[[str], Any]:
    """Provide a function to load skill modules in tests using common.skills_path."""

    def _loader(skill_name: str):
        return load_skill_module(skill_name)

    return _loader


# =============================================================================
# Module Loading Fixtures
# =============================================================================


@pytest.fixture
def reload_modules() -> dict:
    """Fixture to help reload modules between tests."""
    _modules_to_clean: set[str] = set()

    def _register(module_name: str):
        _modules_to_clean.add(module_name)

    def _cleanup():
        for name in list(_modules_to_clean):
            if name in sys.modules:
                del sys.modules[name]
            _modules_to_clean.discard(name)

    yield {"register": _register, "cleanup": _cleanup}

    # Cleanup after test
    _cleanup()


# =============================================================================
# Singleton Reset Fixtures
# =============================================================================


@pytest.fixture
def reset_singletons():
    """
    Reset all singletons before and after test.

    This ensures test isolation by clearing any cached state.
    """
    # Reset before
    import agent.core.registry as reg_module
    import agent.core.skill_manager as sm_module
    import agent.core.skill_registry as sr_module

    # Reset registry singletons
    reg_module.SkillRegistry._instance = None
    sr_module.SkillRegistry._instance = None

    # Reset skill manager singletons
    sm_module._skill_manager = None
    sm_module._manager = None

    yield

    # Reset after
    reg_module.SkillRegistry._instance = None
    sr_module.SkillRegistry._instance = None
    sm_module._skill_manager = None
    sm_module._manager = None


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP FastMCP server."""
    mock = MagicMock()
    mock.list_tools = AsyncMock(return_value=[])
    mock.list_prompts = AsyncMock(return_value=[])
    mock.list_resources = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_inference():
    """Create a mock inference client."""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Mocked inference response")
    return mock


# =============================================================================
# Fake Implementations Fixtures
# =============================================================================


@pytest.fixture
def fake_vector_store():
    """Create a FakeVectorStore for testing."""
    from tests.fakes import FakeVectorStore

    store = FakeVectorStore()
    yield store
    # Cleanup is automatic since it's in-memory


@pytest.fixture
def fake_mcp_server():
    """Create a FakeMCPServer for testing."""
    from tests.fakes import FakeMCPServer

    server = FakeMCPServer()
    yield server
    server.clear()


@pytest.fixture
def fake_inference():
    """Create a FakeInference for testing."""
    from tests.fakes import FakeInference

    inference = FakeInference()
    yield inference
    inference.clear_responses()
    inference.reset()


@pytest.fixture
def fake_registry():
    """Create a FakeSkillRegistry for testing."""
    from tests.fakes import FakeSkillRegistry

    registry = FakeSkillRegistry()
    yield registry
    registry.clear()


# =============================================================================
# Thread Cleanup Fixtures
# =============================================================================


@pytest.fixture
def cleanup_threads():
    """
    Cleanup background threads - use only when needed.

    This is NOT autouse to speed up most tests.
    Only use in tests that start background threads.
    """
    yield
    try:
        from agent.core.bootstrap import shutdown_background_tasks

        shutdown_background_tasks(timeout=2.0)
    except ImportError:
        pass


# =============================================================================
# Common Assertion Helpers
# =============================================================================


@pytest.fixture
def assert_match():
    """Provide assertion helpers for common patterns."""

    def _assert_contains(haystack: str, needle: str, msg: str = ""):
        assert needle in haystack, f"{msg} Expected '{needle}' in '{haystack[:100]}...'"

    def _assert_not_contains(haystack: str, needle: str, msg: str = ""):
        assert needle not in haystack, f"{msg} Unexpected '{needle}' in '{haystack[:100]}...'"

    def _assert_type(obj: Any, expected_type: type, msg: str = ""):
        assert isinstance(obj, expected_type), f"{msg} Expected {expected_type}, got {type(obj)}"

    def _assert_has_attr(obj: Any, attr: str, msg: str = ""):
        assert hasattr(obj, attr), f"{msg} Object missing attribute '{attr}'"

    def _assert_equal(actual: Any, expected: Any, msg: str = ""):
        assert actual == expected, f"{msg} Expected {expected!r}, got {actual!r}"

    return {
        "contains": _assert_contains,
        "not_contains": _assert_not_contains,
        "type": _assert_type,
        "has_attr": _assert_has_attr,
        "equal": _assert_equal,
    }


# =============================================================================
# Async Event Loop Fixtures (Deprecated)
# =============================================================================

# NOTE: The run_async fixture has been removed.
# Use @pytest.mark.asyncio decorator instead of asyncio.run() for async tests.
# This ensures proper event loop management with pytest-asyncio.
#
# Example:
#     @pytest.mark.asyncio
#     async def test_feature(isolated_registry):
#         result = await isolated_registry.load_skill("git", mock_mcp_server)
#         assert result[0] is True


# =============================================================================
# Test Isolation Helpers
# =============================================================================


@pytest.fixture
def clean_modules():
    """
    Clean up specific modules after test.

    Usage:
        def test_something(clean_modules):
            clean_modules.add("agent.core.router")
            ...
    """
    to_clean: set[str] = set()

    def add(module: str):
        to_clean.add(module)

    yield {"add": add}

    # Clean up
    for name in list(to_clean):
        if name in sys.modules:
            del sys.modules[name]
        to_clean.discard(name)


@pytest.fixture
def sandboxed_test():
    """
    Run test with isolated module state.

    Restores sys.modules to its state before the test.
    """
    modules_before = set(sys.modules.keys())

    yield

    # Remove any new modules
    modules_after = set(sys.modules.keys())
    for name in modules_after - modules_before:
        if name.startswith("agent.") or name.startswith("common."):
            del sys.modules[name]
