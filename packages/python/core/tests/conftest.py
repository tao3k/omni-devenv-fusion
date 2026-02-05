"""omni.core tests configuration and fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# Test Stratification Markers
# =============================================================================
#
# Tests are categorized into three tiers:
# - unit: Pure unit tests (mock all external dependencies)
# - local: Local integration tests (real services, no network calls)
# - cloud: Cloud integration tests (requires network/CI environment)
#
# Usage:
#   pytest -m unit       # Run unit tests only
#   pytest -m local     # Run local integration tests
#   pytest -m cloud     # Run cloud integration tests
#   pytest              # Run all tests
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers for test stratification."""
    config.addinivalue_line(
        "markers", "unit: marks tests as pure unit tests (mock all dependencies)"
    )
    config.addinivalue_line(
        "markers", "local: marks tests as local integration tests (real services, no network)"
    )
    config.addinivalue_line(
        "markers", "cloud: marks tests as cloud integration tests (requires network/CI)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running (for performance tracking)"
    )


# Core specific fixtures are now loaded from omni-test-kit-core plugin


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the test session.

    Critical for Rust singletons (lazy_static) to avoid "Event loop is closed" errors.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Import shared fixtures and plugins from core/tests
from .fixtures.core_fixtures import *  # noqa: F403
from .plugins.seed_manager import pytest_configure  # noqa: F401


@pytest.fixture
def skills_path(tmp_path: Path) -> Path:
    """Create a temporary skills directory structure."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a sample skill structure
    sample_skill = skills_dir / "sample"
    sample_skill.mkdir()
    (sample_skill / "SKILL.md").write_text("""---
name: sample
version: 1.0.0
description: A sample skill for testing
""")
    scripts_dir = sample_skill / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")

    return skills_dir


@pytest.fixture
def git_skill_path(tmp_path: Path) -> Path:
    """Create a git skill directory for testing."""
    skills_dir = tmp_path / "skills"
    git_dir = skills_dir / "git"
    git_dir.mkdir()

    # SKILL.md
    (git_dir / "SKILL.md").write_text("""---
name: git
version: 1.0.0
description: Git operations skill
""")

    # scripts/
    scripts_dir = git_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")

    # status.py
    (scripts_dir / "status.py").write_text('''"""Git status command."""
def git_status():
    """Get git status."""
    return "Clean"
__all__ = ["git_status"]
''')

    return git_dir
