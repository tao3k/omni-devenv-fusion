"""
Pytest Configuration and Common Fixtures for Omni-Dev Fusion Test Suite.

This module uses pytest_plugins to load fixtures from the fixtures/ directory.
Plugin-based loading provides better organization and discoverability.

Fixtures are organized into:
    - plugins/: Pytest plugins for seed management and utilities
    - fixtures/core.py: Session-scoped path fixtures
    - fixtures/registry.py: Skill registry and manager fixtures
    - fixtures/mocks.py: Mock objects for testing
    - fixtures/skills_data.py: Factory fixtures for test skills

Usage:
    pytest will automatically discover and load this conftest.py
    Fixtures from fixtures/*.py are loaded via pytest_plugins.

Example:
    async def test_something(isolated_registry, skill_factory):
        skill_dir = skill_factory("test_skill", content="...")
        ...
"""

import pytest
import sys
from pathlib import Path

# Use common.skills_path for skills directory (SSOT from settings.yaml)
from common.skills_path import SKILLS_DIR
from common.gitops import get_project_root

_PROJECT_ROOT = get_project_root()


# =============================================================================
# Session Initialization - Ensure agent.skills is loaded for pytest-xdist
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def _ensure_agent_skills_loaded():
    """Ensure agent.skills package is loaded for all tests.

    This fixes ModuleNotFoundError when running tests with pytest-xdist
    by ensuring the package is loaded before any test workers start.
    """
    import agent.skills
    import agent.skills.core

    assert "agent.skills" in sys.modules
    assert "agent.skills.core" in sys.modules

    yield


@pytest.fixture(scope="session", autouse=True)
def _add_skills_to_syspath():
    """Add assets/skills to sys.path so skill imports work.

    Skills like agent.skills.git.scripts.prepare are in assets/skills/
    but need to be importable as Python packages.
    """
    import sys
    from common.skills_path import SKILLS_DIR

    skills_path = str(SKILLS_DIR())
    if skills_path not in sys.path:
        sys.path.insert(0, skills_path)

    yield


# =============================================================================
# Pytest Plugin-based Fixture Loading
# =============================================================================


pytest_plugins = [
    "plugins.seed_manager",  # Seed synchronization for deterministic tests
    "fixtures.core",
    "fixtures.registry",
    "fixtures.mocks",
    "fixtures.skills_data",
]


# =============================================================================
# Parallel Execution Safety Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _cleanup_singletons():
    """Clean up singletons between tests for parallel execution safety.

    This fixture runs automatically for every test to ensure that
    singleton instances are reset, preventing state leakage between
    tests when running with pytest-xdist.
    """
    import agent.core.skill_runtime.context as ctx

    # Store original state
    original_instance = getattr(ctx, "_instance", None)
    original_manager = getattr(ctx, "_manager", None)

    yield

    # Cleanup after test
    ctx._instance = None
    ctx._manager = None


# =============================================================================
# Legacy Compatibility Aliases (for existing tests)
# =============================================================================


# Provide backward-compatible aliases for tests that haven't been migrated
@pytest.fixture
def skills_base_path(fixtures_core_skills_path) -> Path:
    """Alias for skills_path for backward compatibility."""
    return fixtures_core_skills_path


# Import these from fixtures for direct access (backward compatibility)
# These are re-exported so existing tests continue to work
@pytest.fixture
def project_root(fixtures_core_project_root) -> Path:
    """Backward-compatible alias for project_root."""
    return fixtures_core_project_root


@pytest.fixture
def skills_path(fixtures_core_skills_path) -> Path:
    """Backward-compatible alias for skills_path."""
    return fixtures_core_skills_path


@pytest.fixture
def registry_fixture(fixtures_registry_registry_fixture):
    """Backward-compatible alias for registry_fixture."""
    return fixtures_registry_registry_fixture


@pytest.fixture
def isolated_registry(fixtures_registry_isolated_registry):
    """Backward-compatible alias for isolated_registry."""
    return fixtures_registry_isolated_registry


@pytest.fixture
def skill_manager_fixture(fixtures_registry_skill_manager_fixture):
    """Backward-compatible alias for skill_manager_fixture."""
    return fixtures_registry_skill_manager_fixture


@pytest.fixture
def mock_mcp_server(fixtures_mocks_mock_mcp_server):
    """Backward-compatible alias for mock_mcp_server."""
    return fixtures_mocks_mock_mcp_server


@pytest.fixture
def mock_inference(fixtures_mocks_mock_inference):
    """Backward-compatible alias for mock_inference."""
    return fixtures_mocks_mock_inference


# =============================================================================
# Async Event Loop Note
# =============================================================================


# NOTE: Use @pytest.mark.asyncio decorator instead of asyncio.run()
# for async tests. This ensures proper event loop management.
#
# Example:
#     @pytest.mark.asyncio
#     async def test_feature(isolated_registry):
#         result = await isolated_registry.load_skill("git", mock_mcp_server)
#         assert result[0] is True
