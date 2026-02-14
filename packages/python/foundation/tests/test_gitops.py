"""
GitOps Tests - Simplified

Tests for omni.foundation.runtime.gitops module - project root detection.
GitOps rule: project root is PRJ_ROOT or git toplevel only; no non-git fallback.
"""

import os
from pathlib import Path

import pytest


def _clear_cache():
    from omni.foundation.runtime.gitops import clear_project_root_cache

    clear_project_root_cache()


@pytest.fixture(autouse=True)
def _reset_gitops_cache():
    """Ensure each test starts with a clean project-root cache (avoids cross-test pollution)."""
    _clear_cache()
    yield
    _clear_cache()


class TestGetProjectRootGitOpsBehavior:
    """GitOps-only behavior: PRJ_ROOT or git toplevel; no fallback."""

    def test_prj_root_takes_precedence(self, monkeypatch, tmp_path):
        """When PRJ_ROOT is set, get_project_root() returns that path (resolved)."""
        monkeypatch.setenv("PRJ_ROOT", str(tmp_path))
        _clear_cache()
        try:
            from omni.foundation.runtime.gitops import get_project_root

            result = get_project_root()
            assert result == tmp_path.resolve()
            assert result.is_absolute()
        finally:
            _clear_cache()
            monkeypatch.delenv("PRJ_ROOT", raising=False)

    def test_prj_root_relative_resolved(self, monkeypatch, tmp_path):
        """PRJ_ROOT with relative path is resolved to absolute."""
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PRJ_ROOT", "a/b")
        _clear_cache()
        try:
            from omni.foundation.runtime.gitops import get_project_root

            result = get_project_root()
            assert result == sub.resolve()
            assert result.is_absolute()
        finally:
            _clear_cache()
            monkeypatch.delenv("PRJ_ROOT", raising=False)

    def test_outside_git_raises_without_prj_root(self, monkeypatch, tmp_path):
        """When cwd is not in a git repo and PRJ_ROOT is unset, RuntimeError is raised."""
        monkeypatch.delenv("PRJ_ROOT", raising=False)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        _clear_cache()
        try:
            from omni.foundation.runtime.gitops import get_project_root

            with pytest.raises(RuntimeError) as exc_info:
                get_project_root()
            msg = str(exc_info.value)
            assert "Not in a git repository" in msg or "PRJ_ROOT" in msg
            assert "CRITICAL" in msg
        finally:
            _clear_cache()

    def test_second_call_returns_cached_value(self):
        """Second call to get_project_root() returns same path without re-resolving."""
        _clear_cache()
        from omni.foundation.runtime.gitops import get_project_root

        first = get_project_root()
        second = get_project_root()
        assert first is second

    def test_after_clear_cache_re_resolves(self, monkeypatch, tmp_path):
        """After clear_project_root_cache(), get_project_root() re-resolves (e.g. new PRJ_ROOT)."""
        from omni.foundation.runtime.gitops import clear_project_root_cache, get_project_root

        original = get_project_root()
        clear_project_root_cache()
        monkeypatch.setenv("PRJ_ROOT", str(tmp_path))
        try:
            result = get_project_root()
            assert result == tmp_path.resolve()
            assert result != original
        finally:
            _clear_cache()
            monkeypatch.delenv("PRJ_ROOT", raising=False)

    def test_git_toplevel_from_subdir_same_as_root(self):
        """When run from repo subdir, get_project_root() returns repo toplevel (git -C cwd)."""
        _clear_cache()
        from omni.foundation.runtime.gitops import get_project_root

        root = get_project_root()
        assert (root / ".git").exists()
        assert root.is_absolute()

    def test_empty_prj_root_falls_back_to_git(self, monkeypatch):
        """Empty PRJ_ROOT is ignored; resolution falls back to git from cwd."""
        monkeypatch.setenv("PRJ_ROOT", "")
        _clear_cache()
        try:
            from omni.foundation.runtime.gitops import get_project_root

            result = get_project_root()
            assert (result / ".git").exists()
        finally:
            _clear_cache()
            monkeypatch.delenv("PRJ_ROOT", raising=False)


class TestClearProjectRootCache:
    """clear_project_root_cache() behavior."""

    def test_clear_allows_re_raise_when_still_invalid(self, monkeypatch, tmp_path):
        """After clear, if still outside git and no PRJ_ROOT, second get_project_root() raises again."""
        monkeypatch.delenv("PRJ_ROOT", raising=False)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        _clear_cache()
        from omni.foundation.runtime.gitops import clear_project_root_cache, get_project_root

        with pytest.raises(RuntimeError):
            get_project_root()
        clear_project_root_cache()
        with pytest.raises(RuntimeError):
            get_project_root()


class TestGetProjectRoot:
    """Test get_project_root() function."""

    def test_returns_path_object(self):
        """Test that get_project_root() returns a Path object."""
        from omni.foundation.runtime.gitops import get_project_root

        result = get_project_root()
        assert isinstance(result, Path)

    def test_returns_existing_directory(self):
        """Test that returned path exists."""
        from omni.foundation.runtime.gitops import get_project_root

        result = get_project_root()
        assert result.exists()
        assert result.is_dir()

    def test_returns_absolute_path(self):
        """Test that returned path is absolute."""
        from omni.foundation.runtime.gitops import get_project_root

        result = get_project_root()
        assert result.is_absolute()

    def test_contains_git_directory(self):
        """Test that project root contains .git directory."""
        from omni.foundation.runtime.gitops import get_project_root

        result = get_project_root()
        assert (result / ".git").exists()


class TestProjectPaths:
    """Test ProjectPaths class."""

    def test_project_paths_has_project_root(self):
        """Test project_root property returns Path."""
        from omni.foundation.runtime.gitops import ProjectPaths

        paths = ProjectPaths()
        assert isinstance(paths.project_root, Path)

    def test_packages_property(self):
        """Test packages property returns Path."""
        from omni.foundation.runtime.gitops import ProjectPaths

        paths = ProjectPaths()
        assert isinstance(paths.packages, Path)

    def test_agent_property(self):
        """Test agent property returns Path."""
        from omni.foundation.runtime.gitops import ProjectPaths

        paths = ProjectPaths()
        agent = paths.agent
        assert isinstance(agent, Path)
        assert "agent" in str(agent)

    def test_add_to_path(self):
        """Test add_to_path() method."""
        from omni.foundation.runtime.gitops import ProjectPaths

        paths = ProjectPaths()
        # Should not raise
        paths.add_to_path("agent")


class TestProjectPathMethods:
    """Test path utility methods on ProjectPaths."""

    def test_project_paths_singleton_instance(self):
        """Test that PROJECT singleton is available."""
        from omni.foundation.runtime.gitops import PROJECT, ProjectPaths

        assert isinstance(PROJECT, ProjectPaths)
        assert PROJECT.project_root.exists()


class TestGitOpsFunctions:
    """Test GitOps utility functions."""

    def test_get_spec_dir(self):
        """Test get_spec_dir() function."""
        from omni.foundation.runtime.gitops import get_spec_dir

        result = get_spec_dir()
        assert isinstance(result, Path)

    def test_get_instructions_dir(self):
        """Test get_instructions_dir() function."""
        from omni.foundation.runtime.gitops import get_instructions_dir

        result = get_instructions_dir()
        assert isinstance(result, Path)
        assert "instructions" in str(result)

    def test_get_docs_dir(self):
        """Test get_docs_dir() function."""
        from omni.foundation.runtime.gitops import get_docs_dir

        result = get_docs_dir()
        assert isinstance(result, Path)
        assert result.exists()

    def test_get_agent_dir(self):
        """Test get_agent_dir() function."""
        from omni.foundation.runtime.gitops import get_agent_dir

        result = get_agent_dir()
        assert isinstance(result, Path)
        assert "agent" in str(result)

    def test_is_git_repo_true(self):
        """Test is_git_repo() returns True for project root."""
        from omni.foundation.runtime.gitops import get_project_root, is_git_repo

        result = is_git_repo(get_project_root())
        assert result is True

    def test_is_project_root_true(self):
        """Test is_project_root() returns True for project root."""
        from omni.foundation.runtime.gitops import get_project_root, is_project_root

        result = is_project_root(get_project_root())
        assert result is True

    def test_is_project_root_false_for_non_root(self, tmp_path):
        """Test is_project_root() returns False for a dir with no project indicators."""
        from omni.foundation.runtime.gitops import is_project_root

        assert is_project_root(tmp_path) is False

    def test_is_git_repo_false_outside_repo(self, tmp_path):
        """Test is_git_repo() returns False for a path that is not in a git repo."""
        from omni.foundation.runtime.gitops import is_git_repo

        assert is_git_repo(tmp_path) is False
