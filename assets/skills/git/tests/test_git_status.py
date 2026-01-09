"""
Sample Test Script - Zero Configuration (Phase 35.1)

Usage:
    def test_git_status(git):  # 'git' fixture auto-injected
        assert git.status().success

No conftest.py, no imports needed!
"""


def test_git_status_returns_success(git):
    result = git.status()
    assert result.success


def test_git_status_has_data(git):
    result = git.status()
    assert hasattr(result, "data")
    assert result.data is not None


def test_git_status_no_error(git):
    result = git.status()
    assert result.error is None
