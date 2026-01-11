# assets/skills/git/tests/test_git_smart_workflow.py
"""
Git Smart Workflow Tests (Phase 36.7)

Tests for the Smart Commit Workflow with LangGraph:
- State schema validation
- Workflow construction
- Retry logic (lefthook format, scope fix)
- Status transitions

Architecture: Tool provides data, LLM provides intelligence.
Flow: prepare -> (LLM Analysis) -> execute
"""

import pytest
from unittest.mock import patch, MagicMock
import subprocess


class TestCommitState:
    """Test commit state schema and factory."""

    def test_create_initial_state(self, git):
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

    def test_create_initial_state_defaults(self, git):
        """Test default values for optional parameters."""
        from agent.skills.git.scripts.commit_state import create_initial_state

        state = create_initial_state()

        assert state["project_root"] == "."
        assert state["workflow_id"] == "default"


class TestScopeFixing:
    """Test commit message scope fixing."""

    def test_fix_scope_exact_match(self, git):
        """Exact scope match should return original message."""
        from agent.skills.git.scripts.smart_workflow import _fix_scope_in_message

        msg = "feat(git): new feature"
        fixed = _fix_scope_in_message(msg, ["git", "core", "docs"])

        assert fixed == msg

    def test_fix_scope_case_insensitive(self, git):
        """Scope matching should be case-insensitive."""
        from agent.skills.git.scripts.smart_workflow import _fix_scope_in_message

        msg = "feat(GIT): new feature"
        fixed = _fix_scope_in_message(msg, ["git", "core", "docs"])

        assert fixed == msg  # Should match due to case-insensitive

    def test_fix_scope_close_match(self, git):
        """Close scope match should be fixed."""
        from agent.skills.git.scripts.smart_workflow import _fix_scope_in_message

        msg = "feat(git-workfow): new feature"  # Typo
        fixed = _fix_scope_in_message(msg, ["git-workflow", "core", "docs"])

        assert "git-workflow" in fixed
        assert "new feature" in fixed

    def test_fix_scope_no_match(self, git):
        """No close match should use first valid scope."""
        from agent.skills.git.scripts.smart_workflow import _fix_scope_in_message

        msg = "feat(unknown-scope): new feature"
        fixed = _fix_scope_in_message(msg, ["git", "core", "docs"])

        # Should fall back to first valid scope
        assert "git" in fixed

    def test_fix_scope_invalid_format(self, git):
        """Invalid message format should return as-is."""
        from agent.skills.git.scripts.smart_workflow import _fix_scope_in_message

        msg = "just a description"
        fixed = _fix_scope_in_message(msg, ["git", "core"])

        assert fixed == msg


class TestWorkflowConstruction:
    """Test workflow graph construction."""

    def test_build_workflow(self, git):
        """Test that workflow builds successfully."""
        from agent.skills.git.scripts.smart_workflow import build_workflow

        workflow = build_workflow()

        # Should return a StateGraph
        assert workflow is not None

    def test_workflow_has_prepare_node(self, git):
        """Test workflow has prepare node."""
        from agent.skills.git.scripts.smart_workflow import build_workflow

        workflow = build_workflow()

        # StateGraph is built successfully with nodes
        assert workflow is not None
        # Just verify the workflow can be compiled (has entry point)
        from langgraph.checkpoint.memory import MemorySaver

        compiled = workflow.compile(checkpointer=MemorySaver(), interrupt_before=["execute"])
        assert compiled is not None


class TestNodeExecute:
    """Test execute node with retry logic."""

    def test_execute_success_first_try(self, git):
        """Test successful commit on first try."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        with patch("agent.skills.git.scripts.smart_workflow._try_commit") as mock_try_commit:
            mock_try_commit.return_value = (True, "abc1234")

            state = {
                "status": "approved",
                "final_message": "feat(git): test",
                "project_root": ".",
            }

            result = node_execute(state)

            assert result["status"] == "completed"
            assert result["commit_hash"] == "abc1234"

    def test_execute_retry_after_format(self, git):
        """Test retry after lefthook format."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        with (
            patch("agent.skills.git.scripts.smart_workflow._get_staged_files") as mock_staged,
            patch("agent.skills.git.scripts.smart_workflow._try_commit") as mock_try_commit,
            patch("agent.skills.git.scripts.smart_workflow.subprocess.run") as mock_run,
        ):
            # First call fails (format), second succeeds
            mock_try_commit.side_effect = [
                (False, "lefthook_format"),  # First commit fails
                (True, "abc1234"),  # Second commit succeeds
            ]

            # First staged has file, after format it's not staged
            mock_staged.side_effect = [
                {"src/a.py", "src/b.py"},  # Before commit
                {"src/a.py"},  # After format (b.py reformatted)
            ]

            # subprocess.run for git add reformatted files
            mock_run.return_value = MagicMock(returncode=0)

            state = {
                "status": "approved",
                "final_message": "feat(git): test",
                "project_root": ".",
            }

            result = node_execute(state)

            assert result["status"] == "completed"
            assert "retry_note" in result
            assert "lefthook format" in result["retry_note"]

    def test_execute_not_approved(self, git):
        """Test execute node skips if not approved."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        state = {
            "status": "pending",
            "final_message": "feat(git): test",
            "project_root": ".",
        }

        result = node_execute(state)

        # Should return unchanged state
        assert result["status"] == "pending"

    def test_execute_no_message(self, git):
        """Test execute node fails gracefully with no message."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        state = {
            "status": "approved",
            "final_message": "",
            "project_root": ".",
        }

        result = node_execute(state)

        assert result["status"] == "failed"
        assert "No commit message" in result["error"]


class TestRetryLogic:
    """Test retry logic edge cases."""

    def test_retry_after_format(self, git):
        """Test retry when format fails then commit succeeds."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        with (
            patch("agent.skills.git.scripts.smart_workflow._get_staged_files") as mock_staged,
            patch("agent.skills.git.scripts.smart_workflow._try_commit") as mock_try_commit,
            patch("agent.skills.git.scripts.smart_workflow.subprocess.run") as mock_run,
        ):
            # First commit fails with format error, second commit succeeds
            mock_try_commit.side_effect = [
                (False, "lefthook_format"),  # First commit fails
                (True, "abc1234"),  # Second commit succeeds after re-stage
            ]

            # Files before and after format
            mock_staged.side_effect = [
                {"src/a.py", "src/b.py"},  # Before first commit
                {"src/a.py"},  # After format (b.py reformatted)
            ]

            mock_run.return_value = MagicMock(returncode=0)

            state = {
                "status": "approved",
                "final_message": "feat(core): test",  # Valid scope
                "project_root": ".",
            }

            result = node_execute(state)

            assert result["status"] == "completed"
            assert result["commit_hash"] == "abc1234"

    def test_retry_scope_fix(self, git):
        """Test retry when invalid scope is fixed."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        with (
            patch("agent.skills.git.scripts.smart_workflow._get_staged_files") as mock_staged,
            patch("agent.skills.git.scripts.smart_workflow._try_commit") as mock_try_commit,
            patch("agent.skills.git.scripts.smart_workflow._get_valid_scopes") as mock_scopes,
        ):
            # First commit fails with invalid scope, second succeeds with fixed scope
            mock_try_commit.side_effect = [
                (False, "invalid_scope"),  # First commit fails
                (True, "abc1234"),  # Second commit succeeds
            ]

            mock_staged.return_value = {"src/a.py"}
            mock_scopes.return_value = ["git", "core"]

            state = {
                "status": "approved",
                "final_message": "feat(invalid-scope): test",
                "project_root": ".",
            }

            result = node_execute(state)

            assert result["status"] == "completed"
            assert "git" in result["final_message"] or "core" in result["final_message"]

    def test_retry_all_failed(self, git):
        """Test when all retry attempts fail."""
        from agent.skills.git.scripts.smart_workflow import node_execute

        with patch("agent.skills.git.scripts.smart_workflow._try_commit") as mock_try_commit:
            mock_try_commit.return_value = (False, "unknown_error")

            state = {
                "status": "approved",
                "final_message": "feat(git): test",
                "project_root": ".",
            }

            result = node_execute(state)

            assert result["status"] == "failed"
            assert "Commit failed after retries" in result["error"]


class TestReviewCard:
    """Test review card formatting."""

    def test_format_review_card_prepared(self, git):
        """Test review card for prepared state."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        state = {
            "status": "prepared",
            "staged_files": ["a.py", "b.py"],
            "diff_content": "diff content",
            "workflow_id": "abc123",
        }

        card = format_review_card(state)

        assert "abc123" in card
        assert "a.py" in card
        assert "b.py" in card
        assert "LLM INSTRUCTION" in card

    def test_format_review_card_empty(self, git):
        """Test review card for empty state."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        state = {"status": "empty"}

        card = format_review_card(state)

        assert "Nothing to commit" in card

    def test_format_review_card_security_violation(self, git):
        """Test review card for security violation."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        state = {
            "status": "security_violation",
            "security_issues": [".env", "secrets.yml"],
        }

        card = format_review_card(state)

        assert "Security Issue" in card
        assert ".env" in card

    def test_format_review_card_completed(self, git):
        """Test review card for completed state."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        state = {
            "status": "completed",
            "commit_hash": "abc123",
            "final_message": "feat(git): test",
        }

        card = format_review_card(state)

        assert "abc123" in card
        assert "Commit Success" in card

    def test_format_review_card_failed(self, git):
        """Test review card for failed state."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        state = {
            "status": "failed",
            "error": "lefthook_format",
        }

        card = format_review_card(state)

        assert "failed" in card.lower()


class TestStatusValues:
    """Test all valid status values."""

    def test_all_status_values(self, git):
        """Verify all expected status values are handled."""
        from agent.skills.git.scripts.smart_workflow import format_review_card

        valid_statuses = [
            "pending",
            "prepared",
            "approved",
            "rejected",
            "completed",
            "security_violation",
            "error",
            "empty",
            "failed",
        ]

        for status in valid_statuses:
            state = {"status": status}
            # Should not raise exception
            card = format_review_card(state)
            assert card is not None
