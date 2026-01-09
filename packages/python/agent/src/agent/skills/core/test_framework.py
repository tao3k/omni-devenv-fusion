"""
agent/skills/core/test_framework.py - Pytest Plugin for Skill Tests

Phase 35.1: Dynamic fixture generation and @test decorator.

Features:
- Auto-discovers skills in assets/skills/
- Dynamically generates fixtures: git, knowledge, filesystem, etc.
- @test decorator for simple test functions
- Zero configuration - just import and use

Usage:
    from agent.skills.core.test_framework import test

    @test
    def test_git_status(git):
        assert git.status().success

    @test
    def test_knowledge_query(knowledge):
        result = knowledge.get_development_context()
        assert result.success
"""

import pytest
import sys
import importlib.util
from pathlib import Path
from typing import Optional, Callable, Any


# =============================================================================
# 1. Dynamic Fixture Generation (Magic Happens Here)
# =============================================================================


def _get_skills_root() -> Path:
    """Get the skills root directory from settings.

    Uses common.skills_path.SKILLS_DIR() which reads from settings.yaml.
    This is the single source of truth for skills directory location.
    """
    from common.skills_path import SKILLS_DIR

    return SKILLS_DIR()


def _load_skill_module(skill_name: str, skills_root: Path):
    """Dynamically load a skill's tools.py module."""
    tools_path = skills_root / skill_name / "tools.py"
    if not tools_path.exists():
        return None

    # Create a unique module name for each skill
    module_name = f"__skill_{skill_name}__"

    # Check if already loaded (avoid re-import)
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    return None


def _create_skill_fixture(skill_name: str):
    """Factory to create a pytest fixture for a skill."""

    @pytest.fixture(name=skill_name)
    def _skill_fixture(skills_root: Path):
        module = _load_skill_module(skill_name, skills_root)
        if module is None:
            pytest.skip(f"Skill '{skill_name}' not found (tools.py missing)")
        return module

    _skill_fixture.__doc__ = f"Auto-generated fixture for '{skill_name}' skill"
    return _skill_fixture


# Get skills root once at module load
_skills_root = _get_skills_root()


# Base fixtures
@pytest.fixture
def skills_root() -> Path:
    """Skills root directory (assets/skills)."""
    return _skills_root


@pytest.fixture
def project_root() -> Path:
    """Project root directory."""
    return _skills_root.parent


# =============================================================================
# 2. Pytest Plugin Hook - Auto-register Fixtures
# =============================================================================


def pytest_configure(config):
    """
    Pytest hook: Auto-register skill fixtures when pytest starts.

    This enables fixtures like 'git', 'knowledge', 'filesystem' automatically.
    """
    if not _skills_root.exists():
        return

    # Register fixtures for each skill directory
    for item in _skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            skill_name = item.name

            # Create the fixture function
            fixture_func = _create_skill_fixture(skill_name)

            # Register with pytest's plugin manager
            config.pluginmanager.register(fixture_func, name=f"skill_fixture_{skill_name}")


def pytest_collection_modifyitems(session, config, items):
    """
    Pytest hook: Called after test collection.
    Can filter, reorder, or modify discovered tests.
    """
    pass


# =============================================================================
# 3. @test Decorator
# =============================================================================


def test(
    func: Optional[Callable] = None,
    *,
    parametrize: Optional[list] = None,
    mark: Optional[pytest.Mark] = None,
):
    """
    Decorator for skill test functions.

    Usage:
        @test
        def test_git_status(git):
            assert git.status().success

        @test(parametrize=["cmd", ["status", "branch", "log"]])
        def test_command_exists(git, cmd):
            assert hasattr(git, cmd)
    """

    def decorator(f):
        wrapped = f
        if parametrize:
            wrapped = pytest.mark.parametrize(*parametrize)(f)
        if mark:
            for m in mark if isinstance(mark, list) else [mark]:
                wrapped = pytest.mark.applymarkers(m)(wrapped)
        return wrapped

    # @test without parens - return function unchanged
    if func is not None:
        return func
    return decorator


# Alias for convenience
test_skill = test

# Re-export pytest.fixture for convenience
fixture = pytest.fixture


# =============================================================================
# 4. Utility Functions
# =============================================================================


def unwrap(result: Any) -> Any:
    """
    Unwrap CommandResult for easier assertions.

    Usage:
        @test
        def test_command(git):
            result = unwrap(git.status())
            assert result.success
    """
    if hasattr(result, "success") and hasattr(result, "data"):
        if result.success:
            return result.data
        raise AssertionError(f"Command failed: {getattr(result, 'error', 'Unknown error')}")
    return result


def list_skills() -> list[str]:
    """List all available skills."""
    if not _skills_root.exists():
        return []
    return [
        item.name
        for item in _skills_root.iterdir()
        if item.is_dir() and not item.name.startswith(("_", "."))
    ]


def get_scripts(skill_name: str) -> list[str]:
    """Get test scripts declared in a skill's tools.py.

    Reads the 'test_scripts' attribute from the loaded skill module.
    """
    import sys

    module_name = f"__skill_{skill_name}__"
    if module_name in sys.modules:
        module = sys.modules[module_name]
        if hasattr(module, "test_scripts"):
            return module.test_scripts
    return []


def clear_registry():
    """Clear any cached skill modules (for testing purposes)."""
    to_remove = [k for k in sys.modules.keys() if k.startswith("__skill_")]
    for k in to_remove:
        del sys.modules[k]


# =============================================================================
# 5. Auto-export Fixtures at Module Level (for pytest discovery)
# =============================================================================

# These will be called at module load time to register fixtures
# Note: The actual registration happens in pytest_configure hook above


# Export for convenience
__all__ = [
    "test",
    "test_skill",
    "fixture",
    "unwrap",
    "list_skills",
    "get_scripts",
    "clear_registry",
    "skills_root",
    "project_root",
]
