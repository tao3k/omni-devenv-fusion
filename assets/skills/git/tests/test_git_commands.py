"""
Git Skill Tests - Trinity Architecture v2.0

Tests for git skill commands using direct script imports.
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestGitScripts:
    """Test git skill scripts can be imported."""

    def test_commit_script_imports(self):
        """Test commit script imports successfully."""
        from git.scripts import commit

        assert hasattr(commit, "commit")

    def test_status_script_imports(self):
        """Test status script imports successfully."""
        from git.scripts import status

        assert hasattr(status, "status")

    def test_prepare_script_imports(self):
        """Test prepare script imports successfully."""
        from git.scripts import prepare

        assert hasattr(prepare, "stage_and_scan")

    def test_smart_commit_workflow_imports(self):
        """Test smart_commit_workflow script imports successfully."""
        from git.scripts import smart_commit_workflow

        assert hasattr(smart_commit_workflow, "smart_commit")


class TestGitCommands:
    """Test git skill commands work correctly."""

    def test_commit_returns_string(self, tmp_path, monkeypatch):
        """Test that commit returns a string result."""
        import subprocess

        from git.scripts import commit

        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init"], capture_output=True)

        result = commit.commit(message="Initial commit")
        assert isinstance(result, str)

    def test_stage_and_scan_returns_dict(self, tmp_path, monkeypatch):
        """Test that stage_and_scan returns a dict."""
        import subprocess

        from git.scripts import prepare

        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "init"], capture_output=True)

        result = prepare.stage_and_scan(root_dir=str(tmp_path))
        assert isinstance(result, dict)
        assert "staged_files" in result
