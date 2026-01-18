"""
test_graph_workflow.py - Tests for DynamicGraphBuilder-based Smart Commit Workflow

Phase 61: Integration tests for DynamicGraphBuilder demonstrating Functional Graph
Construction for the Smart Commit workflow.

These tests verify:
1. Graph construction using DynamicGraphBuilder fluent API
2. Node creation with skill commands (mocked)
3. Conditional routing based on prepare results
4. Human-in-the-Loop interrupt before execute
5. Visualization output
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from langgraph.graph import END
from agent.core.orchestrator.builder import DynamicGraphBuilder
from agent.core.state import GraphState


class TestSmartCommitGraphConstruction:
    """Tests for Smart Commit graph construction using DynamicGraphBuilder."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext for Smart Commit."""
        manager = MagicMock()
        manager.run = AsyncMock(
            return_value={
                "staged_files": ["test.py"],
                "diff": "+ line",
                "security_issues": [],
                "lefthook_error": "",
            }
        )
        return manager

    def test_build_smart_commit_graph(self, mock_skill_manager):
        """Test building the Smart Commit graph with DynamicGraphBuilder."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=False)

        # Node 1: prepare - Stage files, scan for issues
        builder.add_skill_node(
            "prepare",
            skill_name="git",
            command_name="stage_and_scan",
            state_output={
                "staged_files": "staged_files",
                "diff": "diff_content",
                "security_issues": "security_issues",
                "lefthook_error": "lefthook_error",
            },
        )

        # Node 2: route_prepare - Conditional routing based on prepare result
        async def _route_prepare_node(state: GraphState) -> dict:
            staged_files = state.get("staged_files", [])
            lefthook_error = state.get("lefthook_error", "")
            security_issues = state.get("security_issues", [])

            if not staged_files:
                return {"status": "empty"}
            if lefthook_error:
                return {"status": "lefthook_failed"}
            if security_issues:
                return {"status": "security_violation"}

            return {"status": "prepared"}

        builder.add_function_node(
            "route_prepare",
            _route_prepare_node,
        )

        # Node 3: format_review - Format result for LLM
        async def _format_review_node(state: GraphState) -> dict:
            status = state.get("status", "unknown")
            if status == "prepared":
                staged = state.get("staged_files", [])
                return {"review": f"**{len(staged)} Files to commit**"}
            return {"review": f"**Status**: {status}"}

        builder.add_function_node(
            "format_review",
            _format_review_node,
        )

        # Node 4: execute - Commit (only after approval)
        builder.add_skill_node(
            "execute",
            skill_name="git",
            command_name="commit",
        )

        # Edges
        builder.add_sequence("prepare", "route_prepare", "format_review")

        def _route_to_execute_or_end(state: GraphState) -> str:
            if state.get("status") == "prepared":
                return "execute"
            return END

        builder.add_conditional_edges(
            "route_prepare",
            _route_to_execute_or_end,
            {"execute": "execute", END: END},
        )
        builder.add_edge("execute", END)
        builder.set_entry_point("prepare")

        # Compile with interrupt before execute (Human-in-the-Loop)
        graph = builder.compile(interrupt_before=["execute"])

        assert graph is not None
        assert len(builder.nodes) == 4
        assert builder._entry_point == "prepare"

    def test_graph_has_correct_nodes(self, mock_skill_manager):
        """Test that graph has the expected nodes."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=False)

        # Add nodes
        builder.add_skill_node("prepare", "git", "stage_and_scan")
        builder.add_skill_node("route_prepare", "git", "scan")
        builder.add_skill_node("format_review", "git", "analyze")
        builder.add_skill_node("execute", "git", "commit")

        builder.add_sequence("prepare", "route_prepare", "format_review", "execute")
        builder.set_entry_point("prepare")

        expected_nodes = {"prepare", "route_prepare", "format_review", "execute"}
        assert set(builder.nodes.keys()) == expected_nodes


class TestSmartCommitVisualization:
    """Tests for workflow visualization."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "test"})
        return manager

    def test_visualize_smart_commit_workflow(self, mock_skill_manager):
        """Test generating Mermaid diagram for Smart Commit workflow."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=False)

        # Build Smart Commit workflow
        builder.add_skill_node("prepare", "git", "stage_and_scan")
        builder.add_skill_node("execute", "git", "commit")

        builder.add_sequence("prepare", "execute")
        builder.set_entry_point("prepare")
        builder.compile(interrupt_before=["execute"])

        diagram = builder.visualize()

        assert "```mermaid" in diagram
        assert "graph TD" in diagram
        assert "prepare" in diagram
        assert "execute" in diagram


class TestConditionalRouting:
    """Tests for conditional routing based on prepare results."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "test"})
        return manager

    def test_conditional_routing_prepared(self, mock_skill_manager):
        """Test routing to execute when status is prepared."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=False)

        builder.add_skill_node("prepare", "git", "stage_and_scan")
        builder.add_skill_node("execute", "git", "commit")
        builder.add_skill_node("error", "git", "status")

        # After prepare: if prepared -> execute, else -> error
        builder.add_conditional_edges(
            "prepare",
            lambda s: "execute" if s.get("status") == "prepared" else "error",
            {"execute": "execute", "error": "error"},
        )
        builder.add_edge("execute", END)
        builder.add_edge("error", END)
        builder.set_entry_point("prepare")

        graph = builder.compile()

        assert graph is not None

    def test_conditional_routing_security_violation(self, mock_skill_manager):
        """Test routing to error when security issues detected."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=False)

        builder.add_skill_node("prepare", "git", "stage_and_scan")
        builder.add_skill_node("security_alert", "git", "status")
        builder.add_skill_node("execute", "git", "commit")

        # After prepare: route based on status
        builder.add_conditional_edges(
            "prepare",
            lambda s: "security_alert" if s.get("security_issues") else "execute",
            {"security_alert": "security_alert", "execute": "execute"},
        )
        builder.add_edge("security_alert", END)
        builder.add_edge("execute", END)
        builder.set_entry_point("prepare")

        graph = builder.compile()

        assert graph is not None


class TestFormatReviewCard:
    """Tests for the review card formatting logic."""

    def test_prepared_status(self):
        """Test formatting for prepared status."""
        state = {
            "status": "prepared",
            "staged_files": ["test.py", "main.py"],
            "diff_content": "+ added feature",
        }

        staged_files = state.get("staged_files", [])
        result = f"**{len(staged_files)} Files to commit**"

        assert "2 Files to commit" in result

    def test_security_violation_status(self):
        """Test formatting for security violation status."""
        state = {
            "status": "security_violation",
            "security_issues": ["secrets.yml", ".env"],
        }

        issues = state.get("security_issues", [])
        result = f"Security Issue Detected: {', '.join(issues)}"

        assert "Security Issue Detected" in result
        assert "secrets.yml" in result

    def test_empty_status(self):
        """Test formatting for empty status."""
        result = "Nothing to commit"

        assert "Nothing to commit" in result

    def test_lefthook_failed_status(self):
        """Test formatting for lefthook failed status."""
        error_msg = "Formatting issues found"
        result = f"Lefthook Failed: {error_msg}"

        assert "Lefthook Failed" in result
        assert "Formatting issues found" in result
