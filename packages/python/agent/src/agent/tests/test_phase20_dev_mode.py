"""
src/agent/tests/test_phase20_dev_mode.py
Phase 20: DevWorkflow Tests - The Self-Evolution Engine.

Tests for:
- DevWorkflow (omni dev command)
- RAG context retrieval
- Claude Code integration
- Post-Mortem audit

Run with: pytest packages/python/agent/src/agent/tests/test_phase20_dev_mode.py -v
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from agent.core.workflows.dev_mode import DevWorkflow, create_dev_workflow
from agent.core.session import SessionManager
from agent.core.ux import UXManager


# =============================================================================
# DevWorkflow Tests
# =============================================================================


class TestDevWorkflow:
    """Test DevWorkflow for feature development lifecycle."""

    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create mock session."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            session = SessionManager("test-dev-workflow")
            return session

    @pytest.fixture
    def mock_ux(self):
        """Create mock UX manager."""
        ux = MagicMock(spec=UXManager)
        ux.console = MagicMock()
        ux.console.print = MagicMock()
        ux.console.rule = MagicMock()
        ux.console.status = MagicMock()
        ux.show_routing_result = MagicMock()
        ux.show_rag_hits = MagicMock()
        ux.show_audit_result = MagicMock()
        return ux

    @pytest.fixture
    def mock_vector_memory(self):
        """Create mock vector memory."""
        memory = MagicMock()
        memory.search = AsyncMock(return_value=[])
        return memory

    def test_workflow_initialization(self, mock_session, mock_ux):
        """DevWorkflow initializes correctly."""
        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
        )

        assert workflow.session == mock_session
        assert workflow.ux == mock_ux
        assert workflow.context_injector is not None
        assert workflow.claude_adapter is not None
        assert workflow.reviewer is not None

    def test_workflow_with_custom_components(self, mock_session, mock_ux, mock_vector_memory):
        """DevWorkflow accepts custom components."""
        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
            vector_memory=mock_vector_memory,
        )

        assert workflow.vector_memory == mock_vector_memory

    @pytest.mark.asyncio
    async def test_plan_and_retrieve(self, mock_session, mock_ux):
        """Plan and retrieve context via RAG."""
        # Create a real vector store for this test
        from agent.core.vector_store import get_vector_memory

        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
            vector_memory=get_vector_memory(),
        )

        result = await workflow._plan_and_retrieve("Add user authentication feature")

        assert "files" in result
        assert "docs" in result
        assert "search_results" in result

    @pytest.mark.asyncio
    async def test_plan_and_retrieve_empty_query(self, mock_session, mock_ux):
        """Handle empty feature request."""
        from agent.core.vector_store import get_vector_memory

        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
            vector_memory=get_vector_memory(),
        )

        result = await workflow._plan_and_retrieve("")

        assert "files" in result
        assert "docs" in result

    def test_build_mission_brief(self, mock_session, mock_ux):
        """Mission brief is built correctly."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        context_info = {
            "files": ["src/auth/models.py", "src/auth/views.py"],
            "docs": ["docs/security/auth.md"],
        }

        brief = workflow._build_mission_brief("Add authentication", context_info)

        assert "Add authentication" in brief
        assert "src/auth/models.py" in brief
        assert "src/auth/views.py" in brief
        assert "docs/security/auth.md" in brief
        assert "Mission Context" in brief
        assert "Relevant Files" in brief

    def test_build_mission_brief_empty_context(self, mock_session, mock_ux):
        """Handle empty context gracefully."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        context_info = {"files": [], "docs": []}

        brief = workflow._build_mission_brief("Simple task", context_info)

        assert "Simple task" in brief
        assert "Mission Context" in brief

    @pytest.mark.asyncio
    async def test_get_git_diff_staged(self, mock_session, mock_ux):
        """Get git diff of staged changes."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        # This might be empty if no staged changes exist
        diff = await workflow._get_git_diff()

        # Just verify it returns a string
        assert isinstance(diff, str)

    @pytest.mark.asyncio
    async def test_get_file_contents(self, mock_session, mock_ux, tmp_path):
        """Read file contents for context."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        contents = await workflow._get_file_contents([str(test_file)])

        assert str(test_file) in contents
        assert contents[str(test_file)] == "print('hello')"

    @pytest.mark.asyncio
    async def test_get_file_contents_missing_file(self, mock_session, mock_ux):
        """Handle missing files gracefully."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        contents = await workflow._get_file_contents(["nonexistent/file.py"])

        assert len(contents) == 0

    @pytest.mark.asyncio
    async def test_verify_changes_empty_diff(self, mock_session, mock_ux):
        """Handle empty git diff."""
        workflow = DevWorkflow(session=mock_session, ux=mock_ux)

        # Mock _get_git_diff to return empty string
        workflow._get_git_diff = AsyncMock(return_value="")

        result = {}
        await workflow._verify_changes("Test feature", result)

        assert result.get("audit_approved") is False
        assert "No changes detected" in result.get("audit_feedback", "")


class TestFactoryFunction:
    """Test factory functions."""

    def test_create_dev_workflow(self, tmp_path):
        """Factory creates workflow correctly."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            # Mock VectorMemory initialization
            with patch("agent.core.vector_store.VectorMemory") as MockVM:
                mock_vm = MagicMock()
                MockVM.return_value = mock_vm

                session = SessionManager("test-factory")
                ux = UXManager()

                workflow = create_dev_workflow(session=session, ux=ux)

                assert isinstance(workflow, DevWorkflow)
                assert workflow.session == session
                assert workflow.ux == ux


class TestDevWorkflowIntegration:
    """Integration tests for DevWorkflow."""

    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create mock session."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            session = SessionManager("test-integration")
            return session

    @pytest.fixture
    def mock_ux(self):
        """Create mock UX manager."""
        ux = MagicMock(spec=UXManager)
        ux.console = MagicMock()
        ux.console.print = MagicMock()
        ux.console.rule = MagicMock()
        ux.show_routing_result = MagicMock()
        ux.show_rag_hits = MagicMock()
        ux.show_audit_result = MagicMock()
        return ux

    @pytest.mark.asyncio
    async def test_full_workflow_with_mocked_claude(self, mock_session, mock_ux, tmp_path):
        """Full workflow execution with mocked Claude Code."""
        from agent.core.vector_store import get_vector_memory
        from agent.core.adapters.claude_cli import ClaudeCodeAdapter

        # Create workflow
        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
            vector_memory=get_vector_memory(),
        )

        # Mock ClaudeCodeAdapter to avoid actual CLI execution
        workflow.claude_adapter = MagicMock(spec=ClaudeCodeAdapter)
        workflow.claude_adapter.run_mission = AsyncMock(
            return_value={
                "success": True,
                "output": "Created scripts/hello.py",
                "exit_code": 0,
                "duration_seconds": 5.0,
            }
        )

        # Mock git diff to return some changes
        with patch("subprocess.check_output") as mock_git:
            mock_git.return_value = "diff --git a/scripts/hello.py b/scripts/hello.py\n+print('hello')"

            # Mock ReviewerAgent audit
            from agent.core.agents.reviewer import AuditResult

            workflow.reviewer = MagicMock()
            workflow.reviewer.audit = AsyncMock(
                return_value=AuditResult(
                    approved=True,
                    feedback="Changes look good",
                    confidence=0.9,
                    issues_found=[],
                    suggestions=[],
                )
            )

            # Run workflow
            result = await workflow.run("Create a hello world script")

            # Verify results
            assert "feature_request" in result
            assert result["success"] is True  # Audit approved
            assert result["audit_approved"] is True

    @pytest.mark.asyncio
    async def test_workflow_logs_to_session(self, mock_session, mock_ux, tmp_path):
        """Workflow logs events to session."""
        from agent.core.vector_store import get_vector_memory

        workflow = DevWorkflow(
            session=mock_session,
            ux=mock_ux,
            vector_memory=get_vector_memory(),
        )

        # Mock Claude and git to avoid actual execution
        from agent.core.adapters.claude_cli import ClaudeCodeAdapter

        workflow.claude_adapter = MagicMock(spec=ClaudeCodeAdapter)
        workflow.claude_adapter.run_mission = AsyncMock(
            return_value={
                "success": True,
                "output": "Done",
                "exit_code": 0,
                "duration_seconds": 1.0,
            }
        )

        with patch("subprocess.check_output", return_value=""):
            from agent.core.agents.reviewer import AuditResult

            workflow.reviewer = MagicMock()
            workflow.reviewer.audit = AsyncMock(
                return_value=AuditResult(
                    approved=False,
                    feedback="No changes",
                    confidence=0.5,
                    issues_found=["no_changes"],
                    suggestions=[],
                )
            )

            await workflow.run("Test feature")

            # Verify session has logged events
            assert len(mock_session.events) > 0

            # Check that workflow events are logged
            event_types = [e["type"] for e in mock_session.events]
            assert "system" in event_types


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestDevModeCLI:
    """Test CLI integration for dev command."""

    def test_dev_command_parsing(self, tmp_path):
        """Test that dev command arguments are parsed correctly."""
        import argparse
        from agent.core.workflows.dev_mode import create_dev_workflow

        # Simulate CLI parsing
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        dev_parser = subparsers.add_parser("dev")
        dev_parser.add_argument("query", nargs="...", help="Feature request")
        dev_parser.add_argument("--resume", type=str)

        args = parser.parse_args(["dev", "Add user authentication"])

        assert args.command == "dev"
        assert args.query == ["Add user authentication"]

    def test_dev_command_with_resume(self, tmp_path):
        """Test dev command with resume flag."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        dev_parser = subparsers.add_parser("dev")
        dev_parser.add_argument("query", nargs="...", help="Feature request")
        dev_parser.add_argument("--resume", type=str)

        args = parser.parse_args(["dev", "--resume", "abc123", "Add feature"])

        assert args.command == "dev"
        assert args.resume == "abc123"
        assert args.query == ["Add feature"]
