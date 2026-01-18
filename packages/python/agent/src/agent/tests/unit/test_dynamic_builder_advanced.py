"""
test_dynamic_builder_advanced.py - Advanced DynamicGraphBuilder Features Tests

Tests for LangGraph v0.2+ advanced features:
1. Human-in-the-Loop with interrupt() API
2. Command pattern for complex graph control
3. State Schema with Reducers
4. Stream Modes
5. Send pattern for parallel execution
6. CompiledGraph helper methods
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Annotated
import operator
from langgraph.graph import END

from agent.core.orchestrator.builder import DynamicGraphBuilder
from agent.core.orchestrator.compiled import CompiledGraph
from agent.core.orchestrator.state_utils import create_reducer_state_schema
from agent.core.state import GraphState
from langgraph.types import Command, Send, interrupt


class TestHumanInTheLoop:
    """Test Human-in-the-Loop interrupt functionality."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"success": True})
        return manager

    def test_add_interrupt_node(self, mock_skill_manager):
        """Test adding an interrupt node."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_interrupt_node(
            "human_review",
            "Please review and approve the commit",
            resume_key="approval",
        )

        assert "human_review" in builder.nodes
        assert builder.nodes["human_review"].type == "interrupt"

    def test_interrupt_with_resume_key(self, mock_skill_manager):
        """Test interrupt node with custom resume key."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_interrupt_node(
            "approval",
            "Approve?",
            resume_key="user_decision",
        )

        assert builder.nodes["approval"].type == "interrupt"

    def test_compiled_graph_has_interrupt(self, mock_skill_manager):
        """Test that compiled graph has interrupt checking methods."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile()

        assert isinstance(graph, CompiledGraph)
        assert hasattr(graph, "has_interrupt")
        assert hasattr(graph, "get_interrupt_value")
        assert hasattr(graph, "resume")
        assert hasattr(graph, "goto")


class TestCommandPattern:
    """Test Command pattern for complex graph control."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"success": True})
        return manager

    def test_add_command_node(self, mock_skill_manager):
        """Test adding a command node."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        async def conditional_node(state):
            if state.get("approved"):
                return Command(update={"status": "done"}, goto="END")
            return Command(update={"status": "skipped"}, goto="END")

        builder.add_command_node("execute", conditional_node)

        assert "execute" in builder.nodes
        assert builder.nodes["execute"].type == "command"

    def test_compiled_graph_resume(self, mock_skill_manager):
        """Test CompiledGraph.resume() method."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-123")

        # Test resume creates Command
        command = graph.resume("approved")
        assert isinstance(command, Command)
        assert command.resume == "approved"

    def test_compiled_graph_resume_with_update(self, mock_skill_manager):
        """Test CompiledGraph.resume() with state update."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-123")

        command = graph.resume("approved", update={"note": "LGTM"})
        assert command.resume == "approved"
        assert command.update == {"note": "LGTM"}

    def test_compiled_graph_goto(self, mock_skill_manager):
        """Test CompiledGraph.goto() method."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.add_skill_node("step2", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-123")

        command = graph.goto("step2")
        assert isinstance(command, Command)
        assert command.goto == "step2"


class TestStateReducers:
    """Test State Schema with Reducers."""

    def test_create_reducer_state_schema(self):
        """Test creating a state schema with reducers."""
        state_schema = create_reducer_state_schema(
            GraphState,
            {
                "files": operator.add,
                "results": lambda d, u: d.update(u) or d,
            },
        )

        assert state_schema is not None

    def test_reducer_for_list_accumulation(self):
        """Test reducer for list accumulation."""
        state_schema = create_reducer_state_schema(
            GraphState,
            {"messages": operator.add},  # messages exists in GraphState
        )

        # Verify Annotated type is present
        annotations = getattr(state_schema, "__annotations__", {})
        assert "messages" in annotations

    def test_reducer_for_dict_merge(self):
        """Test reducer for dictionary merge."""
        state_schema = create_reducer_state_schema(
            GraphState, {"results": lambda d, u: d.update(u) or d}
        )

        assert state_schema is not None


class TestCompiledGraphHelpers:
    """Test CompiledGraph helper methods."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "test"})
        return manager

    def test_get_config(self, mock_skill_manager):
        """Test config generation."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-thread")

        config = graph.get_config()
        assert config == {"configurable": {"thread_id": "test-thread"}}

        # Override thread_id
        config = graph.get_config("other-thread")
        assert config == {"configurable": {"thread_id": "other-thread"}}

    def test_get_state(self, mock_skill_manager):
        """Test state retrieval."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-thread")

        # Should return None if no state exists yet
        state = graph.get_state()
        # State may be None if no execution has occurred

    def test_get_next_node(self, mock_skill_manager):
        """Test next node detection."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.add_skill_node("step2", "test", "cmd")
        builder.add_sequence("step1", "step2")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-thread")

        next_node = graph.get_next_node()
        # Initially should be "step1" (entry point)

    def test_has_interrupt_false_before_execution(self, mock_skill_manager):
        """Test has_interrupt returns False before execution."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        graph = builder.compile(thread_id="test-thread")

        # Before execution, no interrupt
        has_interrupt = graph.has_interrupt()
        assert has_interrupt is False


class TestStreamModes:
    """Test Stream Modes configuration."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "test"})
        return manager

    def test_with_stream_modes(self, mock_skill_manager):
        """Test setting stream modes."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        builder.with_stream_modes(["values", "messages"])

        graph = builder.compile()

        assert graph.stream_modes == ["values", "messages"]

    def test_stream_method_uses_configured_modes(self, mock_skill_manager):
        """Test that stream uses configured modes."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("step1", "test", "cmd")
        builder.set_entry_point("step1")

        builder.with_stream_modes(["values"])

        graph = builder.compile()

        # Stream method should exist and use the configured mode
        assert hasattr(graph, "stream")
        assert hasattr(graph, "astream")


class TestVisualization:
    """Test visualization with new node types."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "test"})
        return manager

    def test_visualize_interrupt_node(self, mock_skill_manager):
        """Test visualization includes interrupt nodes."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_interrupt_node("review", "Please review")
        builder.add_skill_node("commit", "git", "commit")
        builder.add_sequence("review", "commit")
        builder.set_entry_point("review")

        diagram = builder.visualize()

        assert "```mermaid" in diagram
        assert "graph TD" in diagram
        assert "review" in diagram
        assert "commit" in diagram
        assert "interrupt" in diagram

    def test_visualize_command_node(self, mock_skill_manager):
        """Test visualization includes command nodes."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        async def conditional_node(state):
            return Command(update={"status": "done"}, goto="END")

        builder.add_command_node("execute", conditional_node)
        builder.add_edge("execute", END)
        builder.set_entry_point("execute")

        diagram = builder.visualize()

        assert "execute" in diagram


class TestSmartCommitUseCase:
    """Test Smart Commit workflow with advanced features."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext for git operations."""
        manager = MagicMock()
        manager.run = AsyncMock(
            return_value={
                "staged_files": ["test.py"],
                "diff": "+ new line",
                "security_issues": [],
            }
        )
        return manager

    def test_smart_commit_with_interrupt(self, mock_skill_manager):
        """Test Smart Commit workflow with human approval interrupt."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        # Stage files
        builder.add_skill_node(
            "stage",
            "git",
            "stage_all",
            state_output={"staged_files": "files"},
        )

        # Human review
        builder.add_interrupt_node(
            "human_review",
            "Please review the changes and approve",
            resume_key="approval",
        )

        # Conditional commit
        async def conditional_commit(state):
            if state.get("approval") in ["approved", "y", "yes"]:
                return Command(
                    update={"status": "committing"},
                    goto="commit",
                )
            return Command(
                update={"status": "skipped"},
                goto=END,
            )

        builder.add_command_node("check_approval", conditional_commit)

        # Commit node
        builder.add_skill_node(
            "commit",
            "git",
            "commit",
            state_input={"message": "commit_message"},
        )

        # Flow
        builder.add_sequence("stage", "human_review", "check_approval")
        builder.add_edge("commit", END)
        builder.set_entry_point("stage")

        # Compile with interrupt
        graph = builder.compile(
            thread_id="smart-commit-123",
        )

        assert isinstance(graph, CompiledGraph)
        assert graph.thread_id == "smart-commit-123"
        assert graph.has_interrupt() is False  # Before execution

    def test_smart_commit_resume_flow(self, mock_skill_manager):
        """Test resuming Smart Commit after approval."""
        builder = DynamicGraphBuilder(mock_skill_manager, checkpoint=True)

        builder.add_skill_node("stage", "git", "stage_all")
        builder.add_skill_node("commit", "git", "commit")
        builder.add_sequence("stage", "commit")
        builder.set_entry_point("stage")

        graph = builder.compile(thread_id="test-123")

        # Resume after approval
        resume_command = graph.resume("approved")
        assert isinstance(resume_command, Command)
        assert resume_command.resume == "approved"


class TestSendPattern:
    """Test Send pattern for parallel execution."""

    @pytest.fixture
    def mock_skill_manager(self):
        """Create a mock SkillContext."""
        manager = MagicMock()
        manager.run = AsyncMock(return_value={"result": "ok"})
        return manager

    def test_add_send_branch(self, mock_skill_manager):
        """Test adding a send branch for parallel execution."""
        builder = DynamicGraphBuilder(mock_skill_manager)

        builder.add_skill_node("spawn", "test", "spawn")
        builder.add_skill_node("task1", "test", "task")
        builder.add_skill_node("task2", "test", "task")
        builder.add_skill_node("aggregate", "test", "aggregate")

        builder.add_send_branch("spawn", ["task1", "task2"])
        builder.add_edge("task1", "aggregate")
        builder.add_edge("task2", "aggregate")
        builder.set_entry_point("spawn")

        graph = builder.compile()

        assert graph is not None
        assert "spawn" in builder.nodes
        assert "task1" in builder.nodes
        assert "task2" in builder.nodes
