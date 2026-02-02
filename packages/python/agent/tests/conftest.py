"""
Centralized Test Fixtures - Agent Layer

Leverages omni-test-kit for common fixtures.
"""

from __future__ import annotations

import pytest
from typing import Any
from pathlib import Path

# Common fixtures like project_root, skills_root, git_test_env are
# automatically loaded from omni-test-kit.


@pytest.fixture
def anyio_backend() -> str:
    """Set the async backend for anyio tests."""
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_dIContainer():
    """Reset the DI container before each test for isolation."""
    try:
        from omni.foundation.api.decorators import _DIContainer

        _DIContainer.clear()
        yield
        _DIContainer.clear()
    except ImportError:
        yield


@pytest.fixture
def test_settings(tmp_path: Path) -> dict[str, Any]:
    """Create test settings for isolation."""
    settings = {
        "test_mode": True,
        "log_level": "DEBUG",
    }
    return settings


@pytest.fixture
def git_skill(skills_root: Path):
    """Load the git skill for testing."""
    from omni.core.skills import UniversalScriptSkill

    git_skill_path = skills_root / "git"
    skill = UniversalScriptSkill("git", str(git_skill_path))
    return skill
