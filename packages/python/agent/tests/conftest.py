"""
Centralized Test Fixtures - Trinity Architecture v2.0

Provides unified fixtures for all tests using PRJ_DIRS for path resolution.
This eliminates hardcoded paths throughout the test suite.

Usage:
    from omni.foundation.config.dirs import PRJ_DIRS, PRJ_CONFIG

    # Or use fixtures directly in tests:
    def test_something(skills_root, project_root):
        assert (skills_root / "git").exists()
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# Path Fixtures (Using SKILLS_DIR and PRJ_DIRS)
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory using git toplevel."""
    from omni.foundation.runtime.gitops import get_project_root

    root = get_project_root()
    assert root.exists(), f"Project root not found: {root}"
    return root


@pytest.fixture
def skills_root() -> Path:
    """Get the skills root directory (assets/skills).

    Uses SKILLS_DIR from omni.foundation.config.skills which correctly
    resolves to assets/skills relative to project root.
    """
    from omni.foundation.config.skills import SKILLS_DIR

    skills = SKILLS_DIR()
    assert skills.exists(), f"Skills directory not found: {skills}"
    return skills


@pytest.fixture
def config_dir() -> Path:
    """Get the config directory (PRJ_CONFIG_HOME)."""
    from omni.foundation.config.dirs import PRJ_DIRS

    return PRJ_DIRS.config_home


@pytest.fixture
def cache_dir() -> Path:
    """Get the cache directory (PRJ_CACHE_HOME)."""
    from omni.foundation.config.dirs import PRJ_DIRS

    return PRJ_DIRS.cache_home


# =============================================================================
# Git Repository Fixtures
# =============================================================================


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
    )

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
    )

    return tmp_path


@pytest.fixture
def git_repo_with_files(git_repo: Path) -> Path:
    """Create a git repo with some files for testing."""
    # Add some test files
    (git_repo / "test.py").write_text("print('test')")
    (git_repo / "data.txt").write_text("some data")

    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add test files"],
        cwd=git_repo,
        capture_output=True,
    )

    return git_repo


# =============================================================================
# Settings Fixtures
# =============================================================================


@pytest.fixture
def test_settings(tmp_path: Path) -> dict[str, Any]:
    """Create test settings for isolation."""
    settings = {
        "test_mode": True,
        "log_level": "DEBUG",
    }
    return settings


# =============================================================================
# Skill Fixtures
# =============================================================================


@pytest.fixture
def git_skill_path(skills_root: Path) -> Path:
    """Get the path to the git skill."""
    return skills_root / "git"


@pytest.fixture
def git_skill(git_skill_path: Path, git_repo: Path):
    """Load the git skill for testing with a temporary git repo."""
    from omni.core.skills import UniversalScriptSkill

    skill = UniversalScriptSkill("git", str(git_skill_path))
    # We don't await load() here to keep fixture sync
    # Tests should handle async loading if needed
    return skill


# =============================================================================
# Utility Fixtures
# =============================================================================


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
