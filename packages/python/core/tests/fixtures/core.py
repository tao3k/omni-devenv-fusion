"""
Core Path Fixtures

Session-scoped path fixtures computed once per test session.
These are loaded automatically as pytest plugins.

Fixtures:
    - project_paths: Session-scoped paths dict
    - project_root: Project root directory
    - skills_path: Skills directory path
    - temp_dir: Temporary directory
"""

from pathlib import Path

import pytest

from omni.foundation.config.skills import SKILLS_DIR
from omni.foundation.runtime.gitops import get_project_root

_PROJECT_ROOT = get_project_root()


@pytest.fixture(scope="session")
def fixtures_core_project_paths() -> dict:
    """Session-scoped paths - computed once per test session."""
    return {
        "root": _PROJECT_ROOT,
        "skills": SKILLS_DIR(),
    }


@pytest.fixture(scope="session")
def fixtures_core_project_root() -> Path:
    """Return the project root directory (session-scoped)."""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_core_skills_path() -> Path:
    """Return the skills directory path (session-scoped)."""
    return SKILLS_DIR()


@pytest.fixture
def fixtures_core_temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for tests."""
    return tmp_path
