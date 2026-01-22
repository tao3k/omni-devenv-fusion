"""
GitOps Tests - Simplified

Tests for omni.foundation.runtime.gitops module - project root detection.
"""

import pytest
from pathlib import Path


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
        from omni.foundation.runtime.gitops import is_git_repo, get_project_root

        result = is_git_repo(get_project_root())
        assert result is True

    def test_is_project_root_true(self):
        """Test is_project_root() returns True for project root."""
        from omni.foundation.runtime.gitops import is_project_root, get_project_root

        result = is_project_root(get_project_root())
        assert result is True
