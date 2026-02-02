"""Git-related test fixtures."""

import subprocess
from pathlib import Path
import pytest


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def git_repo(temp_git_repo):
    """Alias for temp_git_repo."""
    return temp_git_repo


@pytest.fixture
def git_test_env(temp_git_repo, monkeypatch):
    """
    Set up a git test environment.

    Changes CWD to the temp repo and clears global caches to ensure
    ConfigPaths and other singletons pick up the new root.
    """
    monkeypatch.chdir(temp_git_repo)
    monkeypatch.delenv("PRJ_ROOT", raising=False)

    # Reset caches to pick up new CWD as project root
    try:
        from omni.foundation.runtime.gitops import clear_project_root_cache

        clear_project_root_cache()

        from omni.foundation.config.dirs import PRJ_DIRS

        PRJ_DIRS.clear_cache()

        # Reset ConfigPaths singletons (both class-level and module-level)
        import omni.foundation.config.paths as paths_module

        paths_module._paths_instance = None
        paths_module.ConfigPaths._instance = None
    except ImportError:
        pass

    return temp_git_repo


@pytest.fixture
def gitops_verifier(git_test_env):
    """Fixture to verify GitOps states in the git test environment."""
    from omni.test_kit.gitops import GitOpsVerifier

    return GitOpsVerifier(git_test_env)
