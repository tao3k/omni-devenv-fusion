"""
Git Smart Workflow Tests

Tests for smart commit workflow functionality.
Uses direct imports from actual modules.
"""

import pytest
from unittest.mock import patch, MagicMock
import subprocess


class TestCommitState:
    """Test commit state schema and factory."""

    def test_create_initial_state(self):
        """Test creating initial commit state."""
        from agent.skills.git.scripts.commit_state import create_initial_state

        state = create_initial_state(project_root="/test", workflow_id="abc123")

        assert state["project_root"] == "/test"
        assert state["workflow_id"] == "abc123"
        assert state["status"] == "pending"
        assert state["staged_files"] == []
        assert state["diff_content"] == ""
        assert state["security_issues"] == []
        assert state["final_message"] == ""
        assert state["commit_hash"] is None
        assert state["error"] is None

    def test_create_initial_state_defaults(self):
        """Test default values for optional parameters."""
        from agent.skills.git.scripts.commit_state import create_initial_state

        state = create_initial_state()

        assert state["project_root"] == "."
        assert state["workflow_id"] == "default"


class TestStageAndScan:
    """Test stage_and_scan function."""

    def test_stage_and_scan_returns_dict(self, tmp_path, monkeypatch):
        """Verify stage_and_scan returns a dictionary."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(tmp_path)

        # Mock subprocess
        def mock_run(cmd, *args, **kwargs):
            return MagicMock(stdout="", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("shutil.which", lambda x: None)

        result = stage_and_scan(str(tmp_path))

        assert isinstance(result, dict)

    def test_stage_and_scan_stages_files(self, tmp_path, monkeypatch):
        """Verify stage_and_scan stages files when there are changes."""
        from agent.skills.git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(tmp_path)

        calls = []

        def mock_run(cmd, *args, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
                return MagicMock(stdout="test.py\n", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("shutil.which", lambda x: None)

        result = stage_and_scan(str(tmp_path))

        # Should have called git add
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) > 0


class TestSmartCommitWorkflow:
    """Test smart commit workflow functions."""

    def test_build_workflow_exists(self):
        """Verify _build_workflow function exists."""
        from agent.skills.git.scripts.smart_commit_workflow import _build_workflow

        assert callable(_build_workflow)

    def test_visualize_workflow_exists(self):
        """Verify visualize_workflow function exists."""
        from agent.skills.git.scripts.smart_commit_workflow import visualize_workflow

        assert callable(visualize_workflow)

    def test_visualize_workflow_returns_string(self):
        """Verify visualize_workflow returns a string."""
        from agent.skills.git.scripts.smart_commit_workflow import visualize_workflow

        result = visualize_workflow()
        assert isinstance(result, str)


class TestCogScopes:
    """Test cog scopes retrieval."""

    def test_get_cog_scopes_returns_list(self):
        """Verify _get_cog_scopes returns a list of scopes."""
        from agent.skills.git.scripts.prepare import _get_cog_scopes

        scopes = _get_cog_scopes()

        assert isinstance(scopes, list)


class TestValidateAndFixScope:
    """Test scope validation."""

    def test_validate_and_fix_scope_exists(self):
        """Verify _validate_and_fix_scope function exists."""
        from agent.skills.git.scripts.prepare import _validate_and_fix_scope

        assert callable(_validate_and_fix_scope)

    def test_validate_and_fix_scope_returns_tuple(self):
        """Verify _validate_and_fix_scope returns a tuple."""
        from agent.skills.git.scripts.prepare import _validate_and_fix_scope

        result = _validate_and_fix_scope("feat", "git")
        assert isinstance(result, tuple)
        assert len(result) == 3  # (valid, scope, suggestions)


class TestCheckLefthook:
    """Test lefthook checking."""

    def test_check_lefthook_exists(self):
        """Verify _check_lefthook function exists."""
        from agent.skills.git.scripts.prepare import _check_lefthook

        assert callable(_check_lefthook)

    def test_check_lefthook_returns_tuple(self):
        """Verify _check_lefthook returns a tuple."""
        from agent.skills.git.scripts.prepare import _check_lefthook

        result = _check_lefthook()
        assert isinstance(result, tuple)
        # (exists, version, output)


class TestCheckSensitiveFiles:
    """Test sensitive file detection."""

    def test_check_sensitive_files_exists(self):
        """Verify _check_sensitive_files function exists."""
        from agent.skills.git.scripts.prepare import _check_sensitive_files

        assert callable(_check_sensitive_files)

    def test_check_sensitive_files_returns_list(self):
        """Verify _check_sensitive_files returns a list."""
        from agent.skills.git.scripts.prepare import _check_sensitive_files

        result = _check_sensitive_files(["test.py", "main.py"])
        assert isinstance(result, list)
