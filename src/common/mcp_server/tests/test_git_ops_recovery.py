"""
Pytest Test Suite for Git Ops Smart Recovery - Auto-Fix Intelligence

Tests cover:
1. Recovery logic for nixfmt formatting failures -> suggests 'just agent-fmt'
2. Recovery logic for vale writing style failures -> suggests 'writer.polish_text'
3. Recovery logic for ruff python linting failures
4. Successful commit returns success status
5. Validation logic for type, scope, and message format

Run: uv run pytest src/common/mcp_server/tests/test_git_ops_recovery.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from common.mcp_core.gitops import get_project_root

PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server" / "executor"))

# Import git_ops module functions
from git_ops import (
    GitRulesCache,
    GitWorkflowCache,
    _validate_type,
    _validate_scope,
    _validate_message_format,
    _execute_smart_commit_with_recovery,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def git_cache():
    """Reset GitRulesCache before each test."""
    GitRulesCache._loaded = False
    GitRulesCache._instance = None
    yield
    GitRulesCache._loaded = False
    GitRulesCache._instance = None


@pytest.fixture
def mock_subprocess(git_cache):
    """Mock subprocess.run with configurable return values."""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_run.return_value = mock_process
        yield mock_process, mock_run


@pytest.fixture
def mock_cache(git_cache):
    """Mock GitRulesCache instance."""
    GitRulesCache._instance = MagicMock()
    GitRulesCache._instance.get_scopes.return_value = ["nix", "mcp", "docs"]
    GitRulesCache._instance.get_types.return_value = ["feat", "fix", "docs"]
    return GitRulesCache._instance


# =============================================================================
# Smart Commit Recovery Tests
# =============================================================================


class TestSmartCommitRecovery:
    """Tests for smart_commit error recovery and suggested fixes."""

    @pytest.mark.parametrize(
        "stdout,expected_fix",
        [
            ("SUMMARY: (fail)\n[nixfmt] reformatted 1 file", "just agent-fmt"),
            ("SUMMARY: (fail)\n[fmt] formatting issues", "just agent-fmt"),
        ],
        ids=["nixfmt_failure", "fmt_failure"],
    )
    def test_formatting_failure_suggests_fmt(
        self, mock_subprocess, mock_cache, stdout, expected_fix
    ):
        """When nixfmt/fmt fails, suggest 'just agent-fmt'."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 1
        mock_process.stdout = stdout
        mock_process.stderr = ""

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="fix", scope="nix", message="format code")
        )
        data = json.loads(result)

        assert data["status"] == "failure"
        assert "Formatting checks failed" in data["analysis"]
        assert data["suggested_fix"] == expected_fix

    def test_vale_failure_suggests_polish_text(self, mock_subprocess, mock_cache):
        """When vale fails, suggest 'writer.polish_text'."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 1
        mock_process.stdout = "SUMMARY: (fail)\n[vale] found 3 issues"
        mock_process.stderr = ""

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="fix", scope="docs", message="update readme")
        )
        data = json.loads(result)

        assert data["status"] == "failure"
        assert "Writing style checks failed" in data["analysis"]
        assert "writer.polish_text" in data["suggested_fix"]

    def test_ruff_failure_suggests_fix(self, mock_subprocess, mock_cache):
        """When ruff fails, suggest fixing python errors."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 1
        mock_process.stdout = "SUMMARY: (fail)\n[ruff] found errors (F401, E501)"
        mock_process.stderr = ""

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="fix", scope="mcp", message="fix lint errors")
        )
        data = json.loads(result)

        assert data["status"] == "failure"
        assert "Python linting failed" in data["analysis"]

    def test_secrets_failure_suggests_immediate_removal(self, mock_subprocess, mock_cache):
        """When secrets detection fails, suggest immediate removal."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 1
        mock_process.stdout = "SUMMARY: (fail)\n[secrets] found API keys"
        mock_process.stderr = ""

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="fix", scope="mcp", message="fix secret leak")
        )
        data = json.loads(result)

        assert data["status"] == "failure"
        assert "Secret detection failed" in data["analysis"]
        assert "Remove secrets from code immediately" in data["suggested_fix"]

    def test_success_returns_success_status(self, mock_subprocess, mock_cache):
        """When commit succeeds, return success status."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 0
        mock_process.stdout = "[master a1b2c3d] fix(mcp): handle timeout"

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="fix", scope="mcp", message="handle timeout")
        )
        data = json.loads(result)

        assert data["status"] == "success"
        assert "output" in data

    def test_raw_output_included_in_failure(self, mock_subprocess, mock_cache):
        """Failure response includes truncated raw output for debugging."""
        mock_process, _ = mock_subprocess
        mock_process.returncode = 1
        mock_process.stdout = "SUMMARY: (fail)\n[vale] found 10 issues in long document..."
        mock_process.stderr = ""

        result = asyncio.run(
            _execute_smart_commit_with_recovery(type="docs", scope="docs", message="update docs")
        )
        data = json.loads(result)

        assert data["status"] == "failure"
        assert "raw_output" in data
        assert len(data["raw_output"]) <= 2000


# =============================================================================
# Validation Logic Tests
# =============================================================================


class TestValidationLogic:
    """Tests for commit message validation functions."""

    @pytest.mark.parametrize(
        "msg_type,expected_valid",
        [
            ("feat", True),
            ("fix", True),
            ("docs", True),
            ("chore", True),
            ("INVALID", False),
            ("feature", False),  # not conventional
        ],
        ids=["feat", "fix", "docs", "chore", "invalid_upper", "invalid_not_conventional"],
    )
    def test_validate_type(self, git_cache, msg_type, expected_valid):
        """Type validation accepts conventional types, rejects others."""
        valid, error = _validate_type(msg_type)
        assert valid == expected_valid
        if not expected_valid:
            assert "Invalid type" in error

    @pytest.mark.parametrize(
        "scope,expected_valid",
        [
            ("nix", True),
            ("mcp", True),
            ("docs", True),
            ("", True),  # empty scope is valid
        ],
        ids=["nix_scope", "mcp_scope", "docs_scope", "empty_scope"],
    )
    def test_validate_scope(self, git_cache, scope, expected_valid):
        """Scope validation works for configured scopes."""
        valid, _ = _validate_scope(scope)
        assert valid == expected_valid

    @pytest.mark.parametrize(
        "message,expected_valid,error_hint",
        [
            ("add new feature", True, None),
            ("fix bug", True, None),
            ("", False, "too short"),
            ("ab", False, "too short"),  # less than 3 chars
            ("Add feature.", False, "period"),  # ends with period
            ("Add Feature", False, "lowercase"),  # starts with uppercase
        ],
        ids=["valid", "valid_short", "empty", "too_short", "ends_period", "starts_uppercase"],
    )
    def test_validate_message_format(self, git_cache, message, expected_valid, error_hint):
        """Message format validation rules."""
        valid, error = _validate_message_format(message)
        assert valid == expected_valid
        if not expected_valid and error_hint:
            assert error_hint.lower() in error.lower()


# =============================================================================
# GitWorkflowCache Tests
# =============================================================================


class TestGitWorkflowCache:
    """Tests for GitWorkflowCache - protocol loaded from gitops.md."""

    @pytest.fixture
    def workflow_cache(self):
        """Reset and return GitWorkflowCache instance."""
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None
        cache = GitWorkflowCache()
        yield cache
        GitWorkflowCache._loaded = False
        GitWorkflowCache._instance = None

    def test_cache_is_singleton(self, workflow_cache):
        """GitWorkflowCache follows singleton pattern."""
        cache2 = GitWorkflowCache()
        assert cache2 is workflow_cache

    def test_default_protocol_is_stop_and_ask(self, workflow_cache):
        """Default protocol should be 'stop_and_ask'."""
        protocol = workflow_cache.get_protocol()
        assert protocol == "stop_and_ask"

    def test_get_rules_returns_dict(self, workflow_cache):
        """get_rules should return a dictionary."""
        rules = workflow_cache.get_rules()
        assert isinstance(rules, dict)

    def test_should_ask_user_without_force(self, workflow_cache):
        """should_ask_user returns True when force_execute=False."""
        assert workflow_cache.should_ask_user(force_execute=False) is True

    def test_should_ask_user_with_force_on_stop_and_ask(self, workflow_cache):
        """should_ask_user returns False when force_execute=True."""
        # force_execute means user has authorized, so don't ask
        assert workflow_cache.should_ask_user(force_execute=True) is False

    def test_protocol_loaded_from_workflow_file(self, workflow_cache):
        """Protocol should be loaded from gitops.md."""
        # The cache should have loaded the file
        assert workflow_cache.protocol in ["stop_and_ask", "auto_commit"]

    def test_reload_functionality(self, workflow_cache):
        """reload() should refresh the cache."""
        original_protocol = workflow_cache.protocol
        workflow_cache.reload()
        # After reload, protocol should still be the same (file didn't change)
        assert workflow_cache.protocol == original_protocol


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
