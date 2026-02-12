"""
test_ui.py - Unit tests for tracer UI components

Tests colored console output and TracedExecution context manager.
"""

from __future__ import annotations

import pytest
from datetime import datetime

from omni.tracer.ui import (
    TracedExecution,
    StepInfo,
    print_header,
    print_step_start,
    print_step_end,
    print_thinking,
    print_memory,
    print_param,
    console,
)


class TestStepInfo:
    """Tests for StepInfo dataclass."""

    def test_create_step_info(self):
        """Test creating StepInfo."""
        step = StepInfo(
            name="test_step",
            step_type="NODE_START",
            step_id="step_001",
            input_data={"query": "test"},
        )

        assert step.name == "test_step"
        assert step.step_type == "NODE_START"
        assert step.step_id == "step_001"
        assert step.input_data == {"query": "test"}
        assert step.status == "pending"
        assert step.thinking is None
        assert step.duration_ms == 0

    def test_step_with_thinking(self):
        """Test StepInfo with thinking content."""
        step = StepInfo(
            name="llm_step",
            step_type="LLM_START",
            step_id="step_002",
            thinking=["First thought", "Second thought"],
        )

        assert len(step.thinking) == 2
        assert step.thinking[0] == "First thought"


class TestTracedExecution:
    """Tests for TracedExecution context manager."""

    @pytest.mark.asyncio
    async def test_set_param(self):
        """Test setting parameters."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            tracer.set_param("$query", "test query")
            tracer.set_param("limit", 10)  # Without $ prefix

        assert tracer._params["$query"] == "test query"
        assert tracer._params["$limit"] == 10

    @pytest.mark.asyncio
    async def test_start_and_end_step(self):
        """Test starting and ending steps."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("test_step", "NODE_START", input_data={"key": "value"})
            assert step_id == "step_001_test_step"
            assert tracer.current_step_id == step_id
            assert tracer.step_count == 1

            tracer.end_step(step_id, output_data={"result": "ok"}, status="completed")

        assert tracer.current_step_id is None
        assert len(tracer._steps) == 1

    @pytest.mark.asyncio
    async def test_record_thinking(self):
        """Test recording thinking content."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("llm", "LLM_START")
            tracer.record_thinking(step_id, "First thought")
            tracer.record_thinking(step_id, "Second thought")

        assert tracer.thinking_count == 2
        step = tracer.get_step(step_id)
        assert step is not None
        assert len(step.thinking) == 2

    @pytest.mark.asyncio
    async def test_save_to_memory(self):
        """Test saving to memory pool."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("step1", "NODE_START")
            tracer.save_to_memory("memory_data", {"key": "value"}, step_id)

        assert "memory_data" in tracer._memory
        assert len(tracer._memory["memory_data"]) == 1

    @pytest.mark.asyncio
    async def test_get_memory_history(self):
        """Test getting memory history."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("step1", "NODE_START")
            tracer.save_to_memory("counter", 1, step_id)

            step_id2 = tracer.start_step("step2", "NODE_START")
            tracer.save_to_memory("counter", 2, step_id2)

            history = tracer.get_memory_history("counter")

        assert len(history) == 2
        assert history[0]["value"] == 1
        assert history[1]["value"] == 2

    @pytest.mark.asyncio
    async def test_nested_steps(self):
        """Test nested step tracking."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step1 = tracer.start_step("parent", "NODE_START")
            step2 = tracer.start_step("child1", "NODE_START")
            step3 = tracer.start_step("child2", "NODE_START")

            assert tracer.current_step_id == step3

            tracer.end_step(step3)
            assert tracer.current_step_id == step2

            tracer.end_step(step2)
            assert tracer.current_step_id == step1

            tracer.end_step(step1)
            assert tracer.current_step_id is None

    @pytest.mark.asyncio
    async def test_get_step(self):
        """Test getting step by ID."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("test", "NODE_START", input_data={"key": "value"})
            step = tracer.get_step(step_id)

        assert step is not None
        assert step.name == "test"
        assert step.input_data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_step_not_found(self):
        """Test getting non-existent step."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step = tracer.get_step("nonexistent")

        assert step is None

    @pytest.mark.asyncio
    async def test_auto_trace_id(self):
        """Test auto-generated trace ID."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            pass

        assert tracer.trace_id is not None
        assert tracer.trace_id.startswith("trace_")

    @pytest.mark.asyncio
    async def test_step_count(self):
        """Test step counting."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            tracer.start_step("step1", "NODE_START")
            tracer.end_step(tracer.current_step_id)

            tracer.start_step("step2", "NODE_START")
            tracer.end_step(tracer.current_step_id)

            tracer.start_step("step3", "NODE_START")
            tracer.end_step(tracer.current_step_id)

        assert tracer.step_count == 3

    @pytest.mark.asyncio
    async def test_thinking_count(self):
        """Test thinking count."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step_id = tracer.start_step("llm", "LLM_START")
            tracer.record_thinking(step_id, "Thought 1")
            tracer.record_thinking(step_id, "Thought 2")
            tracer.record_thinking(step_id, "Thought 3")

        assert tracer.thinking_count == 3

    @pytest.mark.asyncio
    async def test_memory_versions(self):
        """Test memory versioning."""
        async with TracedExecution("test_task", stream_to_console=False) as tracer:
            step1 = tracer.start_step("step1", "NODE_START")
            tracer.save_to_memory("plan", "v1", step1)

            step2 = tracer.start_step("step2", "NODE_START")
            tracer.save_to_memory("plan", "v2", step2)

            step3 = tracer.start_step("step3", "NODE_START")
            tracer.save_to_memory("plan", "v3", step3)

        history = tracer.get_memory_history("plan")
        assert len(history) == 3
        assert history[0]["value"] == "v1"
        assert history[1]["value"] == "v2"
        assert history[2]["value"] == "v3"


class TestConsoleFunctions:
    """Tests for console output functions."""

    def test_print_param(self):
        """Test print_param function."""
        # Should not raise
        print_param("$query", "test value")

    def test_print_header(self):
        """Test print_header function."""
        # Should not raise
        print_header("Test Header", "test_001")

    def test_print_step_start(self):
        """Test print_step_start function."""
        # Should not raise
        print_step_start("test_step", "NODE_START", "step_001", {"key": "value"})

    def test_print_step_end(self):
        """Test print_step_end function."""
        # Should not raise
        print_step_end("test_step", "completed", 10.5, {"result": "ok"})

    def test_print_thinking(self):
        """Test print_thinking function."""
        # Should not raise
        print_thinking("llm", "This is a thinking process")

    def test_print_memory(self):
        """Test print_memory function."""
        # Should not raise
        print_memory("memory_data", {"key": "value"}, "step_001", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
