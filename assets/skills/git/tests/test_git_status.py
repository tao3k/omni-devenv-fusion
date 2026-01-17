"""
Git Status Tests - Direct import pattern

Tests for git status functionality using direct function imports.
"""


def test_status_module_exists():
    """Verify status module exists."""
    from agent.skills.git.scripts import status

    assert hasattr(status, "status")
    assert callable(status.status)


def test_status_returns_string():
    """Verify status function returns a string."""
    from agent.skills.git.scripts import status
    from common.gitops import get_project_root

    result = status.status(project_root=get_project_root())
    assert isinstance(result, str)


def test_git_status_detailed_exists():
    """Verify git_status_detailed function exists."""
    from agent.skills.git.scripts import status

    assert hasattr(status, "git_status_detailed")
    assert callable(status.git_status_detailed)


def test_has_staged_files_exists():
    """Verify has_staged_files function exists."""
    from agent.skills.git.scripts import status

    assert hasattr(status, "has_staged_files")
    assert callable(status.has_staged_files)


def test_has_unstaged_files_exists():
    """Verify has_unstaged_files function exists."""
    from agent.skills.git.scripts import status

    assert hasattr(status, "has_unstaged_files")
    assert callable(status.has_unstaged_files)
