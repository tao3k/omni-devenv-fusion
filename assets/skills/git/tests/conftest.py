"""Safety guards for git skill tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git_head(repo_root: Path) -> str | None:
    """Return current HEAD for a repository, or None when unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


@pytest.fixture(autouse=True)
def _protect_workspace_head():
    """Fail fast if a test accidentally commits to the workspace repository."""
    workspace_root = Path(__file__).resolve().parents[4]
    before = _git_head(workspace_root)
    yield
    after = _git_head(workspace_root)
    assert before == after, (
        "git skill tests must not mutate workspace HEAD. "
        "Use temp_git_repo and explicit cwd/project_root."
    )
