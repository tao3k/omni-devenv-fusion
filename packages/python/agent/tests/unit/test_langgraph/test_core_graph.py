"""
test_core_graph.py - Tests for OmniGraph

Tests for:
- OmniGraph initialization
- Plan/Execute/Reflect nodes
- Graph execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from omni.langgraph.graph import (
    OmniGraph,
    get_graph,
    reset_graph,
    plan_node,
    execute_node,
    reflect_node,
    should_continue,
    audit_decision,
    GraphInput,
    GraphOutput,
)
from omni.langgraph.state import create_initial_state


class TestOmniGraph:
    """Tests for OmniGraph class."""

    @pytest.fixture
    def mock_inference(self):
        """Create a mock inference client."""
        mock = MagicMock()
        mock.complete = AsyncMock(
            return_value={
                "success": True,
                "content": '{"task_brief": "Test task", "target_agent": "coder", "confidence": 0.8}',
                "tool_calls": [],
            }
        )
        return mock

    @pytest.fixture
    def mock_skill_runner(self):
        """Create a mock skill runner."""
        mock = MagicMock()
        mock.run = AsyncMock(return_value="Skill result")
        return mock

    def test_initialization(self, mock_inference, mock_skill_runner):
        """Should initialize with dependencies."""
        graph = OmniGraph(
            inference_client=mock_inference,
            skill_runner=mock_skill_runner,
        )

        assert graph.inference is mock_inference
        assert graph.skill_runner is mock_skill_runner
        assert graph._app is None

    def test_get_app(self, mock_inference, mock_skill_runner):
        """Should compile workflow on first call."""
        graph = OmniGraph(
            inference_client=mock_inference,
            skill_runner=mock_skill_runner,
        )

        app = graph.get_app()
        assert app is not None
        assert graph._app is app

    def test_get_app_cached(self, mock_inference, mock_skill_runner):
        """Should return cached app on subsequent calls."""
        graph = OmniGraph(
            inference_client=mock_inference,
            skill_runner=mock_skill_runner,
        )

        app1 = graph.get_app()
        app2 = graph.get_app()
        assert app1 is app2


class TestNodeFunctions:
    """Tests for individual node functions."""

    @pytest.fixture
    def base_state(self):
        """Create a base state for testing."""
        return create_initial_state(
            messages=[{"role": "user", "content": "Fix the bug"}],
        )

    @pytest.mark.asyncio
    async def test_plan_node_with_router(self, base_state):
        """Should use router for planning if available."""
        mock_router = MagicMock()
        mock_router.route = AsyncMock(
            return_value={
                "task_brief": "Fix the bug in main.py",
                "target_agent": "filesystem",
                "confidence": 0.9,
                "constraints": [],
                "relevant_files": ["main.py"],
            }
        )

        result = await plan_node(base_state, router=mock_router)

        assert result["current_plan"] == "Fix the bug in main.py"
        assert result["workflow_state"]["target_agent"] == "filesystem"
        assert result["workflow_state"]["route_confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_plan_node_without_router(self, base_state):
        """Should use fallback planning without router."""
        result = await plan_node(base_state, router=None, inference=None)

        assert result["current_plan"] == "Fix the bug"
        assert result["workflow_state"]["target_agent"] == "default"

    @pytest.mark.asyncio
    async def test_execute_node_with_skill_runner(self, base_state):
        """Should execute using skill runner."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value="File content")

        state = {
            **base_state,
            "current_plan": "Read main.py",
            "workflow_state": {"target_agent": "filesystem"},
        }

        result = await execute_node(state, skill_runner=mock_runner)

        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"
        assert "File content" in result["messages"][0]["content"]
        mock_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_node_no_runner(self, base_state):
        """Should handle no skill runner."""
        state = {
            **base_state,
            "current_plan": "Test task",
            "workflow_state": {"target_agent": "test"},
        }

        result = await execute_node(state, skill_runner=None, inference=None)

        assert "Cannot execute" in result["messages"][0]["content"]
        assert result["error_count"] == 1


class TestEdgeLogic:
    """Tests for edge condition functions."""

    def test_should_continue_first_execution(self):
        """Should go to execute on first pass."""
        state = {
            "messages": [{"role": "user", "content": "Test"}],
            "workflow_state": {},
        }

        result = should_continue(state)
        assert result == "execute"

    def test_should_continue_after_execution_coder(self):
        """Should go to reflect for coder tasks."""
        state = {
            "messages": [
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Done"},
            ],
            "workflow_state": {"target_agent": "coder"},
        }

        result = should_continue(state)
        assert result == "reflect"

    def test_should_continue_after_execution_default(self):
        """Should end for default tasks."""
        state = {
            "messages": [
                {"role": "user", "content": "Test"},
                {"role": "assistant", "content": "Done"},
            ],
            "workflow_state": {"target_agent": "default"},
        }

        result = should_continue(state)
        assert result == "__end__"

    def test_audit_decision_approved(self):
        """Should end when approved."""
        state = {
            "workflow_state": {"approved": True},
            "error_count": 0,
        }

        result = audit_decision(state)
        assert result == "__end__"

    def test_audit_decision_retry_needed(self):
        """Should retry when not approved and under limit."""
        state = {
            "workflow_state": {"approved": False},
            "error_count": 1,
        }

        result = audit_decision(state)
        assert result == "execute"

    def test_audit_decision_max_retries(self):
        """Should end when max retries exceeded."""
        state = {
            "workflow_state": {"approved": False},
            "error_count": 5,  # Over limit
        }

        result = audit_decision(state)
        assert result == "__end__"


class TestGraphFactory:
    """Tests for graph factory functions."""

    def test_get_graph_singleton(self):
        """Should return same graph instance."""
        reset_graph()

        graph1 = get_graph()
        graph2 = get_graph()
        assert graph1 is graph2

    def test_reset_graph(self):
        """Should reset the graph instance."""
        graph1 = get_graph()
        reset_graph()
        graph2 = get_graph()

        assert graph1 is not graph2


class TestGraphInputOutput:
    """Tests for GraphInput and GraphOutput TypedDicts."""

    def test_graph_input(self):
        """Should create valid GraphInput."""
        inp: GraphInput = {
            "user_query": "Fix the bug",
            "context": {"file": "main.py"},
        }

        assert inp["user_query"] == "Fix the bug"
        assert inp["context"]["file"] == "main.py"

    def test_graph_output(self):
        """Should create valid GraphOutput."""
        out: GraphOutput = {
            "success": True,
            "content": "Fixed!",
            "confidence": 0.9,
            "iterations": 3,
            "approved": True,
        }

        assert out["success"] is True
        assert out["confidence"] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
