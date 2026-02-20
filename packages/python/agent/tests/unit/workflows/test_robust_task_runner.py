"""
Unit tests for robust_task.runner: run_robust_task and _node_display.
"""

import inspect

import pytest

from omni.agent.workflows.robust_task.runner import (
    _node_display,
    run_robust_task,
)


class TestRunRobustTaskAPI:
    """Test run_robust_task public API and signature."""

    def test_run_robust_task_importable(self):
        assert callable(run_robust_task)

    def test_run_robust_task_signature(self):
        sig = inspect.signature(run_robust_task)
        params = list(sig.parameters)
        assert "request" in params
        assert "console" in params
        assert "thread_id" in params

    def test_run_robust_task_is_async(self):
        assert inspect.iscoroutinefunction(run_robust_task)


class TestNodeDisplay:
    """Test _node_display mapping for streaming panels."""

    def test_returns_tuple_of_three(self):
        content, style, icon = _node_display("unknown", {"foo": "bar"})
        assert isinstance(content, str)
        assert isinstance(style, str)
        assert isinstance(icon, str)

    def test_review_node(self):
        content, style, icon = _node_display("review", {})
        assert "approval" in content.lower() or "Waiting" in content
        assert "yellow" in style
        assert icon == "✋"

    def test_discovery_node_empty(self):
        content, style, icon = _node_display("discovery", {})
        assert "Discovering" in content
        assert style == "magenta"
        assert icon == "🔍"

    def test_discovery_node_with_tools(self):
        state = {
            "discovered_tools": [
                {"tool": "git.commit", "score": 0.9, "description": "Commit changes"},
                {"tool": "skill.other", "score": 0.5, "description": "Other"},
            ]
        }
        content, style, icon = _node_display("discovery", state)
        assert "Found 2 relevant tools" in content
        assert "git.commit" in content
        assert style == "magenta"
        assert icon == "🔍"

    def test_clarify_node_with_goal(self):
        content, style, icon = _node_display("clarify", {"clarified_goal": "Implement feature X"})
        assert "Implement feature X" in content
        assert "Goal" in content
        assert style == "yellow"
        assert icon == "🤔"

    def test_plan_node_with_steps(self):
        state = {
            "plan": {
                "steps": [
                    {"id": "1", "description": "Step one"},
                    {"id": "2", "description": "Step two"},
                ]
            }
        }
        content, style, icon = _node_display("plan", state)
        assert "Plan (2 steps)" in content
        assert "Step one" in content
        assert "Step two" in content
        assert style == "blue"
        assert icon == "📝"

    def test_validate_node_success(self):
        content, style, icon = _node_display("validate", {"validation_result": {"is_valid": True}})
        assert "Success" in content
        assert "green" in style
        assert icon == "🎉"

    def test_validate_node_failure(self):
        content, style, icon = _node_display(
            "validate",
            {"validation_result": {"is_valid": False, "feedback": "Tests failed"}},
        )
        assert "Tests failed" in content
        assert "red" in style
        assert icon == "❌"

    def test_summary_node_with_final_summary(self):
        content, style, icon = _node_display(
            "summary", {"final_summary": "## Done\nTask completed."}
        )
        assert "Done" in content
        assert "Task completed" in content
        assert "magenta" in style
        assert icon == "📄"
