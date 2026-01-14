"""
Unit tests for Tracer.

Tests structured tracing for observability.
"""

import json
import pytest
from unittest.mock import MagicMock

from agent.core.planner.tracer import (
    Tracer,
    TraceEvent,
    TracedExecutor,
    create_tracer,
)


class TestTraceEvent:
    """Tests for TraceEvent."""

    def test_trace_event_creation(self) -> None:
        """Verify trace event creation."""
        event = TraceEvent(
            event_type="task_start",
            trace_id="trace_123",
            span_id="span_456",
            parent_id=None,
            data={"task_id": "t1"},
        )

        assert event.event_type == "task_start"
        assert event.trace_id == "trace_123"
        assert event.span_id == "span_456"
        assert event.parent_id is None
        assert event.data["task_id"] == "t1"
        assert event.timestamp is not None

    def test_trace_event_with_parent(self) -> None:
        """Verify trace event with parent span."""
        event = TraceEvent(
            event_type="tool_call",
            trace_id="trace_123",
            span_id="span_789",
            parent_id="span_456",
            data={"tool": "read_file"},
        )

        assert event.parent_id == "span_456"

    def test_trace_event_to_dict(self) -> None:
        """Verify trace event serializes to dict."""
        event = TraceEvent(
            event_type="test",
            trace_id="trace_123",
            span_id="span_456",
            parent_id=None,
            data={"key": "value"},
        )

        data = event.to_dict()

        assert data["event_type"] == "test"
        assert data["trace_id"] == "trace_123"
        assert data["span_id"] == "span_456"
        assert data["data"]["key"] == "value"
        assert "timestamp" in data

    def test_trace_event_to_json(self) -> None:
        """Verify trace event serializes to JSON."""
        event = TraceEvent(
            event_type="test",
            trace_id="trace_123",
            span_id="span_456",
            parent_id=None,
            data={},
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "test"
        assert parsed["trace_id"] == "trace_123"


class TestTracer:
    """Tests for Tracer class."""

    def test_tracer_initialization(self) -> None:
        """Verify tracer initializes with defaults."""
        tracer = Tracer()

        assert tracer.enabled is True
        assert tracer.trace_id is None

    def test_tracer_disabled(self) -> None:
        """Verify disabled tracer returns empty strings."""
        tracer = Tracer(enabled=False)

        result = tracer.start_trace("plan_1", "Test goal")

        assert result == ""
        assert tracer.trace_id is None

    def test_start_trace(self) -> None:
        """Verify start_trace creates a new trace."""
        tracer = Tracer()

        trace_id = tracer.start_trace("plan_123", "Test goal")

        assert trace_id.startswith("trace_")
        assert tracer.trace_id == trace_id
        assert len(tracer._spans) == 1

        event = tracer._spans[0]
        assert event.event_type == "plan_start"
        assert event.data["plan_id"] == "plan_123"
        assert event.data["goal"] == "Test goal"

    def test_end_trace(self) -> None:
        """Verify end_trace adds final event."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")

        tracer.end_trace("completed")

        assert len(tracer._spans) == 2
        end_event = tracer._spans[-1]
        assert end_event.event_type == "plan_end"
        assert end_event.data["status"] == "completed"

    def test_start_task(self) -> None:
        """Verify start_task adds event and sets current span."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")

        span_id = tracer.start_task("task_1", "First task")

        assert span_id is not None
        assert span_id.startswith("task_")
        assert tracer._current_span_id == span_id

        event = tracer._spans[-1]
        assert event.event_type == "task_start"
        assert event.data["task_id"] == "task_1"
        assert event.data["description"] == "First task"

    def test_end_task(self) -> None:
        """Verify end_task adds event."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")
        tracer.start_task("task_1", "Task")

        tracer.end_task("task_1", "completed", "Result")

        event = tracer._spans[-1]
        assert event.event_type == "task_end"
        assert event.data["task_id"] == "task_1"
        assert event.data["status"] == "completed"

    def test_log_tool_call(self) -> None:
        """Verify log_tool_call adds event."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")

        tracer.log_tool_call("read_file", {"path": "/test"}, "content")

        event = tracer._spans[-1]
        assert event.event_type == "tool_call"
        assert event.data["tool"] == "read_file"
        assert event.data["arguments"]["path"] == "/test"

    def test_log_review(self) -> None:
        """Verify log_review adds event."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")

        tracer.log_review("task_1", "continue", "Task completed")

        event = tracer._spans[-1]
        assert event.event_type == "review"
        assert event.data["task_id"] == "task_1"
        assert event.data["status"] == "continue"

    def test_get_spans(self) -> None:
        """Verify get_spans returns all spans."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")
        tracer.start_task("task_1", "Task")
        tracer.end_task("task_1", "completed")
        tracer.end_trace("completed")

        spans = tracer.get_spans()

        assert len(spans) == 4
        assert spans[0]["event_type"] == "plan_start"
        assert spans[1]["event_type"] == "task_start"
        assert spans[2]["event_type"] == "task_end"
        assert spans[3]["event_type"] == "plan_end"

    def test_get_span_tree(self) -> None:
        """Verify get_span_tree returns tree structure."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")
        tracer.start_task("task_1", "Task")
        tracer.log_tool_call("tool", {}, "result")
        tracer.end_task("task_1", "completed")
        tracer.end_trace("completed")

        tree = tracer.get_span_tree()

        assert "trace_id" in tree
        assert "roots" in tree
        assert "spans" in tree
        assert len(tree["roots"]) == 1

    def test_export_json(self) -> None:
        """Verify export_json returns valid JSON."""
        tracer = Tracer()
        tracer.start_trace("plan_1", "Goal")
        tracer.end_trace("completed")

        json_str = tracer.export_json()
        parsed = json.loads(json_str)

        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_create_tracer_factory(self) -> None:
        """Verify factory function creates tracer."""
        tracer = create_tracer(enabled=True)

        assert isinstance(tracer, Tracer)
        assert tracer.enabled is True


class TestTracedExecutor:
    """Tests for TracedExecutor wrapper."""

    def test_traced_executor_creation(self) -> None:
        """Verify TracedExecutor initializes."""
        mock_executor = MagicMock()
        tracer = Tracer()

        wrapped = TracedExecutor(mock_executor, tracer)

        assert wrapped.executor == mock_executor
        assert wrapped.tracer == tracer

    def test_traced_executor_default_tracer(self) -> None:
        """Verify TracedExecutor uses default tracer."""
        mock_executor = MagicMock()

        wrapped = TracedExecutor(mock_executor)

        assert wrapped.tracer is not None
        assert isinstance(wrapped.tracer, Tracer)
