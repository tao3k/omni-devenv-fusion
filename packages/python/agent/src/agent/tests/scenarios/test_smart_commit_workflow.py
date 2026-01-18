"""
tests/scenarios/test_smart_commit_workflow.py

Phase 36.x: Smart Commit Workflow Integration Tests.

Tests the complete smart commit workflow with real git operations:
1. stage_and_scan - File staging and security scanning
2. Lefthook integration - Pre-commit hook handling
3. Re-stage logic - Capturing files modified by lefthook (e.g., formatting)

Usage:
    uv run pytest packages/python/agent/src/agent/tests/scenarios/test_smart_commit_workflow.py -v
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestSmartCommitWorkflow:
    """Integration tests for smart commit workflow."""

    @pytest.fixture
    def temp_git_repo(self, tmp_path):
        """Create a temporary git repository for testing."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True
        )

        yield repo_path

        # Cleanup
        import shutil

        shutil.rmtree(repo_path, ignore_errors=True)

    @pytest.fixture
    def temp_git_repo_with_uncommitted(self, tmp_path):
        """Create a temp git repo with uncommitted changes."""
        repo_path = tmp_path / "test_repo_uncommitted"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True
        )

        # Add uncommitted changes
        (repo_path / "feature.py").write_text("def hello():\n    print('hello')\n")
        (repo_path / "config.yaml").write_text("setting: value\n")

        yield repo_path

        # Cleanup
        import shutil

        shutil.rmtree(repo_path, ignore_errors=True)

    def test_stage_and_scan_empty_repo(self, temp_git_repo):
        """Test stage_and_scan on repo with no changes."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        result = stage_and_scan(str(temp_git_repo))

        assert result["staged_files"] == []
        assert result["diff"] == ""
        assert result["security_issues"] == []
        assert result["lefthook_error"] == ""

    def test_stage_and_scan_uncommitted_files(self, temp_git_repo_with_uncommitted):
        """Test stage_and_scan correctly stages uncommitted files."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        result = stage_and_scan(str(temp_git_repo_with_uncommitted))

        assert "feature.py" in result["staged_files"]
        assert "config.yaml" in result["staged_files"]
        assert "def hello()" in result["diff"]

    def test_stage_and_scan_respects_sensitive_files(self, tmp_path):
        """Test that sensitive files are detected and unstaged."""
        import os
        from agent.skills.git.scripts.prepare import stage_and_scan

        repo_path = tmp_path / "sensitive_test"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)

        # Add sensitive file in the repo
        original_cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            (repo_path / ".env").write_text("API_KEY=secret123\n")
            (repo_path / "feature.py").write_text("def hello():\n    pass\n")

            # Now run stage_and_scan - it should detect .env as sensitive
            result = stage_and_scan(".")

            # Sensitive file should be detected and removed
            assert ".env" in result["security_issues"]
            # Regular file should still be staged
            assert "feature.py" in result["staged_files"]
        finally:
            os.chdir(original_cwd)

    def test_stage_and_scan_re_stages_lefthook_modified_files(self, tmp_path):
        """Test that files modified by lefthook are re-staged."""
        import os
        from agent.skills.git.scripts.prepare import stage_and_scan, _run

        repo_path = tmp_path / "lefthook_test"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)

        # Add Python file with initial content
        py_file = repo_path / "feature.py"
        py_file.write_text("def hello():\n    print('hello world')\n")

        # Change to repo dir for glob to work
        original_cwd = os.getcwd()
        try:
            os.chdir(repo_path)

            # Stage the file initially
            _run(["git", "add", "."], cwd=repo_path)

            # Verify it's staged
            staged_before, _, _ = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_path)
            assert "feature.py" in staged_before

            # Now simulate lefthook modifying the file (e.g., formatter adds comment)
            py_file.write_text(
                "def hello():\n    print('hello world')\n    # formatted by lefthook\n"
            )

            # The file is now modified in working dir but staged version is old
            # When lefthook runs and modifies files, they become unstaged from git's perspective

            # Run stage_and_scan which should re-stage the modified file
            result = stage_and_scan(".")

            # The file should be staged with its formatted content
            assert "feature.py" in result["staged_files"]
            assert "formatted by lefthook" in result["diff"]
        finally:
            os.chdir(original_cwd)

    def test_stage_and_scan_handles_lefthook_failure(self, tmp_path):
        """Test that lefthook failures are properly reported."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        repo_path = tmp_path / "lefthook_fail_test"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)

        # Add a file
        (repo_path / "feature.py").write_text("def hello():\n    pass\n")

        # Mock lefthook to fail
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            if cmd and cmd[0] == "lefthook":
                return MagicMock(returncode=1, stdout="", stderr="Lint failed")
            return original_run(cmd, **kwargs)

        with patch.object(subprocess, "run", side_effect=mock_run):
            result = stage_and_scan(str(repo_path))

        assert result["lefthook_error"] == "Lint failed"

    def test_get_cog_scopes_from_temp_repo(self, tmp_path):
        """Test _get_cog_scopes reads from cog.toml in temp repo."""
        from agent.skills.git.scripts.prepare import _get_cog_scopes

        repo_path = tmp_path / "cog_test"
        repo_path.mkdir()

        # Create cog.toml with scopes
        (repo_path / "cog.toml").write_text(
            '[tool.conventionalcommits]\nscopes = ["core", "agent", "docs"]\n'
        )

        scopes = _get_cog_scopes(repo_path)

        assert "core" in scopes
        assert "agent" in scopes
        assert "docs" in scopes

    def test_get_cog_scopes_returns_empty_when_no_file(self, tmp_path):
        """Test _get_cog_scopes returns empty list when cog.toml doesn't exist."""
        from agent.skills.git.scripts.prepare import _get_cog_scopes

        repo_path = tmp_path / "no_cog"
        repo_path.mkdir()

        # Patch get_project_root to return temp repo so test is isolated
        with patch("common.gitops.get_project_root", return_value=repo_path):
            scopes = _get_cog_scopes(repo_path)

        assert scopes == []


class TestSmartCommitWorkflowEdgeCases:
    """Edge case tests for smart commit workflow."""

    def test_stage_and_scan_nonexistent_repo(self):
        """Test stage_and_scan handles non-existent repository."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        result = stage_and_scan("/nonexistent/path/to/repo")

        # Should return empty results without crashing
        assert result["staged_files"] == []

    def test_stage_and_scan_git_add_failure(self, tmp_path, monkeypatch):
        """Test stage_and_scan handles git add failure gracefully."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        repo_path = tmp_path / "git_fail_test"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)

        # Add uncommitted file
        (repo_path / "feature.py").write_text("def hello():\n    pass\n")

        # Mock git add to fail
        original_run = subprocess.run

        def mock_run(cmd, **kwargs):
            if cmd and cmd[0] == "git" and cmd[1] == "add":
                raise subprocess.CalledProcessError(1, cmd, stderr="Git add failed")
            return original_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Should not crash
        result = stage_and_scan(str(repo_path))
        assert "staged_files" in result

    def test_stage_and_scan_unicode_handling(self, tmp_path):
        """Test stage_and_scan handles unicode content gracefully."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        repo_path = tmp_path / "unicode_test"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)

        # Add file with unicode
        (repo_path / "unicode.py").write_text(
            "# -*- coding: utf-8 -*-\ndef 你好():\n    print('Hello 世界')\n"
        )

        result = stage_and_scan(str(repo_path))

        assert "unicode.py" in result["staged_files"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
