"""
test_tracer.py - Unit tests for the tracer module

Tests core tracing functionality including:
- Step creation and management
- Memory pool operations
- Trace serialization
- Callback system
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime

from omni.tracer import (
    DispatchMode,
    StepType,
    ExecutionStep,
    MemoryPool,
    ExecutionTrace,
    ExecutionTracer,
    LoggingCallback,
    InMemoryTraceStorage,
)


class TestStepType:
    """Tests for StepType enum."""

    def test_step_type_values(self):
        """Test that all expected step types exist."""
        assert StepType.LLM_START.value == "llm_start"
        assert StepType.LLM_END.value == "llm_end"
        assert StepType.TOOL_START.value == "tool_start"
        assert StepType.TOOL_END.value == "tool_end"
        assert StepType.RETRIEVAL.value == "retrieval"
        assert StepType.REASONING.value == "reasoning"
        assert StepType.NODE_START.value == "node_start"
        assert StepType.NODE_END.value == "node_end"


class TestExecutionStep:
    """Tests for ExecutionStep dataclass."""

    def test_create_step(self):
        """Test creating an execution step."""
        step = ExecutionStep(
            step_id="step_123",
            step_type=StepType.LLM_START,
            name="test_llm",
            input_data={"prompt": "Hello"},
        )

        assert step.step_id == "step_123"
        assert step.step_type == StepType.LLM_START
        assert step.name == "test_llm"
        assert step.input_data == {"prompt": "Hello"}
        assert step.status == "pending"
        assert step.reasoning_content is None

    def test_step_serialization(self):
        """Test step to/from dict."""
        step = ExecutionStep(
            step_id="step_456",
            step_type=StepType.TOOL_START,
            name="test_tool",
            input_data={"arg": "value"},
            status="completed",
            duration_ms=100.5,
        )

        # Serialize
        data = step.to_dict()

        assert data["step_id"] == "step_456"
        assert data["step_type"] == "tool_start"
        assert data["name"] == "test_tool"
        assert data["input_data"] == {"arg": "value"}
        assert data["status"] == "completed"
        assert data["duration_ms"] == 100.5

        # Deserialize
        restored = ExecutionStep.from_dict(data)

        assert restored.step_id == step.step_id
        assert restored.step_type == step.step_type
        assert restored.name == step.name


class TestMemoryPool:
    """Tests for MemoryPool."""

    def test_save_and_get(self):
        """Test saving and retrieving from memory."""
        pool = MemoryPool()

        pool.save("result", {"data": "value"}, "step_1")

        entries = pool.get("result")
        assert entries is not None
        assert len(entries) == 1
        assert entries[0].value == {"data": "value"}
        assert entries[0].source_step == "step_1"

    def test_get_latest(self):
        """Test getting latest value of a variable."""
        pool = MemoryPool()

        pool.save("counter", 1, "step_1")
        pool.save("counter", 2, "step_2")
        pool.save("counter", 3, "step_3")

        latest = pool.get_latest("counter")
        assert latest is not None
        assert latest.value == 3
        assert latest.source_step == "step_3"

    def test_get_history(self):
        """Test getting full history of a variable."""
        pool = MemoryPool()

        pool.save("x", 10, "step_a")
        pool.save("x", 20, "step_b")
        pool.save("x", 30, "step_c")

        history = pool.get_history("x")

        assert len(history) == 3
        assert history[0][1] == 10  # timestamp, value, source_step
        assert history[1][1] == 20
        assert history[2][1] == 30

    def test_summary(self):
        """Test memory pool summary."""
        pool = MemoryPool()

        pool.save("a", 1, "s1")
        pool.save("b", 2, "s2")
        pool.save("a", 3, "s3")
        pool.save("a", 4, "s4")

        summary = pool.summary()

        assert summary["a"] == 3
        assert summary["b"] == 1


class TestExecutionTrace:
    """Tests for ExecutionTrace."""

    def test_create_trace(self):
        """Test creating an execution trace."""
        trace = ExecutionTrace(
            trace_id="trace_123",
            user_query="Test query",
            thread_id="session_1",
        )

        assert trace.trace_id == "trace_123"
        assert trace.user_query == "Test query"
        assert trace.thread_id == "session_1"
        assert trace.success is True
        assert trace.step_count() == 0
        assert trace.thinking_step_count() == 0

    def test_add_steps_to_trace(self):
        """Test adding steps to a trace."""
        trace = ExecutionTrace(trace_id="trace_456")

        step1 = ExecutionStep(
            step_id="s1",
            step_type=StepType.NODE_START,
            name="plan",
            input_data={"query": "test"},
        )
        step2 = ExecutionStep(
            step_id="s2",
            step_type=StepType.NODE_END,
            name="plan",
            output_data={"plan": "do stuff"},
        )

        trace.steps["s1"] = step1
        trace.steps["s2"] = step2

        assert trace.step_count() == 2

    def test_trace_serialization(self):
        """Test trace serialization."""
        trace = ExecutionTrace(
            trace_id="trace_789",
            user_query="Serialization test",
        )

        step = ExecutionStep(
            step_id="s1",
            step_type=StepType.LLM_START,
            name="llm",
            reasoning_content="Thinking...",
        )
        trace.steps["s1"] = step

        # Serialize
        data = trace.to_dict()

        assert data["trace_id"] == "trace_789"
        assert data["user_query"] == "Serialization test"
        assert "s1" in data["steps"]
        assert data["steps"]["s1"]["reasoning_content"] == "Thinking..."

    def test_get_thinking_steps(self):
        """Test getting steps with thinking content."""
        trace = ExecutionTrace(trace_id="trace_think")

        step1 = ExecutionStep(
            step_id="s1",
            step_type=StepType.LLM_START,
            name="llm",
            reasoning_content="Thinking about...",
        )
        step2 = ExecutionStep(
            step_id="s2",
            step_type=StepType.TOOL_START,
            name="tool",
        )
        step3 = ExecutionStep(
            step_id="s3",
            step_type=StepType.LLM_END,
            name="llm",
            reasoning_content="Final answer...",
        )

        trace.steps["s1"] = step1
        trace.steps["s2"] = step2
        trace.steps["s3"] = step3

        thinking_steps = trace.get_thinking_steps()

        assert len(thinking_steps) == 2
        assert "s1" in [s.step_id for s in thinking_steps]
        assert "s3" in [s.step_id for s in thinking_steps]


class TestExecutionTracer:
    """Tests for ExecutionTracer."""

    def test_start_and_end_step(self):
        """Test starting and ending a step."""
        tracer = ExecutionTracer(trace_id="tracer_test")

        step_id = tracer.start_step(
            name="test_step",
            step_type=StepType.NODE_START,
            input_data={"test": True},
        )

        assert step_id is not None
        assert tracer.current_step_id == step_id

        tracer.end_step(step_id, output_data={"result": "ok"})

        assert tracer.current_step_id is None
        assert tracer.trace.step_count() == 1

    def test_record_thinking(self):
        """Test recording thinking content."""
        tracer = ExecutionTracer(trace_id="tracer_think")

        step_id = tracer.start_step(name="llm", step_type=StepType.LLM_START)

        tracer.record_thinking(step_id, "Step 1: ")
        tracer.record_thinking(step_id, "Step 2: ")
        tracer.record_thinking(step_id, "Step 3")

        step = tracer.trace.steps[step_id]
        assert step.reasoning_content == "Step 1: Step 2: Step 3"

    def test_memory_pool(self):
        """Test memory pool operations in tracer."""
        tracer = ExecutionTracer(trace_id="tracer_memory")

        step_id = tracer.start_step(name="process", step_type=StepType.NODE_START)

        tracer.save_to_memory("result", {"computed": True}, step_id)
        tracer.save_to_memory("counter", 42, step_id)

        assert tracer.get_memory("result") == {"computed": True}
        assert tracer.get_memory("counter") == 42

    def test_global_variables(self):
        """Test global variable operations."""
        tracer = ExecutionTracer(trace_id="tracer_global")

        tracer.set_global("user_id", "user_123")
        tracer.set_global("session", "active")

        assert tracer.get_global("user_id") == "user_123"
        assert tracer.get_global("session") == "active"
        assert tracer.get_global("nonexistent") is None

    def test_trace_lifecycle(self):
        """Test starting and ending a trace."""
        tracer = ExecutionTracer(trace_id="tracer_lifecycle")

        tracer.start_step(name="start", step_type=StepType.CHAIN_START)
        tracer.end_step(tracer.current_step_id, status="completed")

        trace = tracer.end_trace(success=True)

        assert trace.trace_id == "tracer_lifecycle"
        assert trace.success is True
        assert trace.end_time is not None
        assert trace.duration_ms is not None
        assert trace.step_count() == 1

    def test_record_memory_with_metadata(self):
        """Test record_memory wraps payload with metadata."""
        tracer = ExecutionTracer(trace_id="tracer_record_memory")

        tracer.record_memory(
            "memory_analysis",
            "improved analysis",
            step="step_a",
            metadata={"iteration": 2},
        )

        latest = tracer.trace.memory_pool.get_latest("memory_analysis")
        assert latest is not None
        assert latest.source_step == "step_a"
        assert isinstance(latest.value, dict)
        assert latest.value["content"] == "improved analysis"
        assert latest.value["metadata"]["iteration"] == 2

    def test_serialize_memory_pool(self):
        """Test memory serialization returns trace-scoped structured payload."""
        tracer = ExecutionTracer(trace_id="tracer_serialize", thread_id="thread_1")
        tracer.set_param("topic", "typed languages")
        tracer.set_global("quality_score", 0.6)
        tracer.save_to_memory("memory_reflection", "missing trade-offs", "step_1")

        payload = tracer.serialize_memory_pool()

        assert payload["trace_id"] == "tracer_serialize"
        assert payload["thread_id"] == "thread_1"
        assert "timestamp" in payload
        assert "memory_reflection" in payload["memory_pool"]
        assert payload["summary"]["memory"]["memory_reflection"] == 1

    def test_write_memory_output(self, tmp_path):
        """Test writing serialized memory payload to disk."""
        tracer = ExecutionTracer(trace_id="tracer_write")
        tracer.save_to_memory("memory_plan", {"steps": 3}, "step_2")

        out = tracer.write_memory_output(output_dir=tmp_path)
        data = json.loads((tmp_path / "tracer_write_memory.json").read_text(encoding="utf-8"))

        assert out == str(tmp_path / "tracer_write_memory.json")
        assert data["trace_id"] == "tracer_write"
        assert "memory_plan" in data["memory_pool"]

    def test_dispatch_mode_accepts_string(self):
        """Test callback dispatch mode can be configured via string."""
        tracer = ExecutionTracer(
            trace_id="dispatch_mode_string",
            callback_dispatch_mode="background",
        )
        assert tracer.callback_dispatch_mode == DispatchMode.BACKGROUND


class TestLoggingCallback:
    """Tests for LoggingCallback."""

    def test_callback_registration(self):
        """Test adding a logging callback to tracer."""
        tracer = ExecutionTracer(trace_id="callback_test")
        callback = LoggingCallback()

        tracer.add_callback(callback)

        assert len(tracer.callbacks._callbacks) == 1

    def test_registered_async_callbacks_are_dispatched_in_sync_flow(self):
        """Test async callbacks execute even when tracer APIs are called synchronously."""

        class _CounterCallback(LoggingCallback):
            def __init__(self):
                self.step_start = 0
                self.step_end = 0
                self.thinking = 0
                self.memory = 0
                self.trace_end = 0

            async def on_step_start(self, trace, step):  # type: ignore[override]
                del trace, step
                self.step_start += 1

            async def on_step_end(self, trace, step):  # type: ignore[override]
                del trace, step
                self.step_end += 1

            async def on_thinking(self, trace, step, content):  # type: ignore[override]
                del trace, step, content
                self.thinking += 1

            async def on_memory_save(self, trace, var_name, value, source_step):  # type: ignore[override]
                del trace, var_name, value, source_step
                self.memory += 1

            async def on_trace_end(self, trace):  # type: ignore[override]
                del trace
                self.trace_end += 1

        tracer = ExecutionTracer(trace_id="callback_dispatch_sync")
        cb = _CounterCallback()
        tracer.add_callback(cb)

        step_id = tracer.start_step(name="demo", step_type=StepType.NODE_START)
        tracer.record_thinking(step_id, "x")
        tracer.save_to_memory("memory_demo", 1, step_id)
        tracer.end_step(step_id)
        tracer.end_trace()

        assert cb.step_start == 1
        assert cb.step_end == 1
        assert cb.thinking == 1
        assert cb.memory == 1
        assert cb.trace_end == 1


class TestInMemoryStorage:
    """Tests for InMemoryTraceStorage."""

    def test_save_and_load(self):
        """Test saving and loading traces."""
        storage = InMemoryTraceStorage()

        trace = ExecutionTrace(trace_id="mem_trace")
        storage.save(trace)

        loaded = storage.load("mem_trace")

        assert loaded is not None
        assert loaded.trace_id == "mem_trace"

    def test_list_traces(self):
        """Test listing traces."""
        storage = InMemoryTraceStorage()

        storage.save(ExecutionTrace(trace_id="t1", user_query="Query 1"))
        storage.save(ExecutionTrace(trace_id="t2", user_query="Query 2"))

        traces = storage.list_traces(limit=10)

        assert len(traces) == 2

    def test_delete_trace(self):
        """Test deleting a trace."""
        storage = InMemoryTraceStorage()

        storage.save(ExecutionTrace(trace_id="delete_me"))
        assert storage.load("delete_me") is not None

        deleted = storage.delete("delete_me")
        assert deleted is True
        assert storage.load("delete_me") is None

    def test_clear(self):
        """Test clearing all traces."""
        storage = InMemoryTraceStorage()

        storage.save(ExecutionTrace(trace_id="a"))
        storage.save(ExecutionTrace(trace_id="b"))

        storage.clear()

        assert storage.list_traces() == []


class TestExecutionTracerParams:
    """Tests for ExecutionTracer parameter handling (UltraRAG $variable convention)."""

    def test_set_param_with_dollar_prefix(self):
        """Test setting parameters with $ prefix."""
        tracer = ExecutionTracer(trace_id="params_test")

        tracer.set_param("$query", "What is RAG?")
        tracer.set_param("$top_k", 5)

        assert tracer.get_param("$query") == "What is RAG?"
        assert tracer.get_param("$top_k") == 5

    def test_set_param_without_dollar_prefix(self):
        """Test setting parameters without $ prefix - auto-adds prefix."""
        tracer = ExecutionTracer(trace_id="params_no_prefix")

        tracer.set_param("query", "Test query")
        tracer.set_param("limit", 10)

        # Should work with or without prefix
        assert tracer.get_param("query") == "Test query"
        assert tracer.get_param("$query") == "Test query"
        assert tracer.get_param("limit") == 10

    def test_get_param_nonexistent(self):
        """Test getting nonexistent parameter returns None."""
        tracer = ExecutionTracer(trace_id="params_missing")

        assert tracer.get_param("$nonexistent") is None
        assert tracer.get_param("missing") is None

    def test_params_stored_correctly(self):
        """Test that params are stored in _params dict."""
        tracer = ExecutionTracer(trace_id="params_storage")

        tracer.set_param("$api_key", "secret123")
        tracer.set_param("temperature", 0.7)

        # Check internal storage
        assert "$api_key" in tracer._params
        assert tracer._params["$api_key"] == "secret123"
        assert "$temperature" in tracer._params
        assert tracer._params["$temperature"] == 0.7


class TestExecutionTracerMemoryConventions:
    """Tests for UltraRAG memory variable conventions."""

    def test_save_memory_prefix(self):
        """Test saving with memory_ prefix - goes to history pool."""
        tracer = ExecutionTracer(trace_id="mem_prefix")

        step_id = tracer.start_step(name="test", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_results", [1, 2, 3], step_id)

        # Should be in memory pool with history
        assert tracer.get_memory("memory_results") == [1, 2, 3]
        history = tracer.get_memory_history("memory_results")
        assert len(history) == 1
        assert history[0][1] == [1, 2, 3]

    def test_save_memory_multiple_history(self):
        """Test memory_* tracks full history."""
        tracer = ExecutionTracer(trace_id="mem_history")

        step1 = tracer.start_step(name="step1", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_plan", "initial plan", step1)

        step2 = tracer.start_step(name="step2", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_plan", "revised plan", step2)

        step3 = tracer.start_step(name="step3", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_plan", "final plan", step3)

        # Latest value
        assert tracer.get_memory("memory_plan") == "final plan"

        # Full history
        history = tracer.get_memory_history("memory_plan")
        assert len(history) == 3
        assert history[0][1] == "initial plan"
        assert history[1][1] == "revised plan"
        assert history[2][1] == "final plan"

    def test_dollar_prefix_param(self):
        """Test $ prefix saves to params, and get_memory retrieves it."""
        tracer = ExecutionTracer(trace_id="dollar_prefix")

        tracer.set_param("$config_value", "test")

        # Should be in params
        assert tracer.get_param("$config_value") == "test"
        # get_memory also returns params for $ prefix (see docs)
        assert tracer.get_memory("$config_value") == "test"

    def test_no_prefix_global(self):
        """Test variables without prefix go to globals."""
        tracer = ExecutionTracer(trace_id="no_prefix")

        tracer.save_to_memory("result", {"status": "ok"}, "step_1")

        # Should be accessible via get_global
        assert tracer.get_global("result") == {"status": "ok"}
        # get_memory also returns globals for non-prefixed vars (see docs)
        assert tracer.get_memory("result") == {"status": "ok"}

    def test_get_memory_summary(self):
        """Test memory summary returns correct counts."""
        tracer = ExecutionTracer(trace_id="mem_summary")

        tracer.set_param("$query", "test")
        tracer.set_param("$top_k", 5)
        tracer.set_global("result", "value")

        step1 = tracer.start_step(name="s1", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_data", [1, 2], step1)

        step2 = tracer.start_step(name="s2", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_data", [3, 4], step2)

        summary = tracer.get_memory_summary()

        assert summary["params"] == 2
        assert summary["globals"] == 1
        assert "memory_data" in summary["memory"]
        assert summary["memory"]["memory_data"] == 2


class TestExecutionTracerStreamCallbacks:
    """Tests for stream callbacks functionality."""

    @pytest.mark.asyncio
    async def test_stream_callback_fires_on_step_start(self):
        """Test stream callback is called on step start."""
        tracer = ExecutionTracer(trace_id="stream_test", enable_stream_callback=True)

        events_received = []

        async def listener(event: str, data: dict):
            events_received.append((event, data))

        tracer.add_stream_listener(listener)

        step_id = tracer.start_step(
            name="test_step", step_type=StepType.NODE_START, input_data={"test": True}
        )

        await tracer.drain_pending_callbacks()

        # Check step_start event was fired
        assert (
            "step_start",
            {"step_id": step_id, "name": "test_step", "step_type": "node_start"},
        ) in events_received

    @pytest.mark.asyncio
    async def test_stream_callback_fires_on_step_end(self):
        """Test stream callback is called on step end."""
        tracer = ExecutionTracer(trace_id="stream_end_test", enable_stream_callback=True)

        events_received = []

        async def listener(event: str, data: dict):
            events_received.append((event, data))

        tracer.add_stream_listener(listener)

        step_id = tracer.start_step(name="end_test", step_type=StepType.NODE_END)
        tracer.end_step(step_id, output_data={"status": "ok"}, status="completed")

        await tracer.drain_pending_callbacks()

        assert (
            "step_end",
            {
                "step_id": step_id,
                "name": "end_test",
                "status": "completed",
                "duration_ms": pytest.approx(0, abs=100),
            },
        ) in events_received

    @pytest.mark.asyncio
    async def test_stream_callback_fires_on_memory_save(self):
        """Test stream callback fires on memory save."""
        tracer = ExecutionTracer(trace_id="stream_mem_test", enable_stream_callback=True)

        events_received = []

        async def listener(event: str, data: dict):
            events_received.append((event, data))

        tracer.add_stream_listener(listener)

        step_id = tracer.start_step(name="mem_step", step_type=StepType.NODE_START)
        tracer.save_to_memory("memory_test", {"key": "value"}, step_id)

        await tracer.drain_pending_callbacks()

        assert (
            "memory_save",
            {"var_name": "memory_test", "source_step": step_id},
        ) in events_received

    @pytest.mark.asyncio
    async def test_stream_callback_fires_on_thinking(self):
        """Test stream callback fires on thinking."""
        tracer = ExecutionTracer(trace_id="stream_think_test", enable_stream_callback=True)

        events_received = []

        async def listener(event: str, data: dict):
            events_received.append((event, data))

        tracer.add_stream_listener(listener)

        step_id = tracer.start_step(name="think_step", step_type=StepType.LLM_START)
        tracer.record_thinking(step_id, "Analyzing...")

        await tracer.drain_pending_callbacks()

        assert ("thinking", {"step_id": step_id, "content": "Analyzing..."}) in events_received

    @pytest.mark.asyncio
    async def test_stream_callback_fires_on_trace_end(self):
        """Test stream callback fires on trace end."""
        tracer = ExecutionTracer(trace_id="stream_trace_end", enable_stream_callback=True)

        events_received = []

        async def listener(event: str, data: dict):
            events_received.append((event, data))

        tracer.add_stream_listener(listener)

        tracer.start_step(name="final", step_type=StepType.CHAIN_END)
        tracer.end_step(tracer.current_step_id, status="completed")
        tracer.end_trace(success=True)

        await tracer.drain_pending_callbacks()

        assert (
            "trace_end",
            {"trace_id": "stream_trace_end", "success": True, "step_count": 1},
        ) in events_received

    def test_no_callback_without_flag(self):
        """Test that callbacks don't fire when flag is disabled."""
        tracer = ExecutionTracer(trace_id="no_callback")

        # Should not raise
        tracer.add_stream_listener(lambda e, d: None)

        step_id = tracer.start_step(name="test", step_type=StepType.NODE_START)
        tracer.end_step(step_id)

    def test_remove_stream_listener(self):
        """Test removing a stream listener."""
        tracer = ExecutionTracer(trace_id="remove_listener")

        async def listener1(_e, _d):
            pass

        async def listener2(_e, _d):
            pass

        tracer.add_stream_listener(listener1)
        tracer.add_stream_listener(listener2)

        assert len(tracer._stream_listeners) == 2

        tracer.remove_stream_listener(listener1)

        assert len(tracer._stream_listeners) == 1
        assert listener2 in tracer._stream_listeners


class TestExecutionTracerContextVariables:
    """Tests for context variable thread-safety."""

    def test_current_step_id_tracking(self):
        """Test current_step_id is tracked correctly."""
        tracer = ExecutionTracer(trace_id="context_test")

        step1 = tracer.start_step(name="step1", step_type=StepType.NODE_START)
        assert tracer.current_step_id == step1

        step2 = tracer.start_step(name="step2", step_type=StepType.NODE_START, parent_step_id=step1)
        assert tracer.current_step_id == step2

        tracer.end_step(step2)
        assert tracer.current_step_id == step1

        tracer.end_step(step1)
        assert tracer.current_step_id is None

    def test_nested_step_tracking(self):
        """Test nested step stack tracking."""
        tracer = ExecutionTracer(trace_id="nested_test")

        step1 = tracer.start_step(name="parent", step_type=StepType.NODE_START)
        step2 = tracer.start_step(name="child1", step_type=StepType.NODE_START)
        step3 = tracer.start_step(name="child2", step_type=StepType.NODE_START)

        assert tracer.current_step_id == step3

        tracer.end_step(step3)
        assert tracer.current_step_id == step2

        tracer.end_step(step2)
        assert tracer.current_step_id == step1

        tracer.end_step(step1)
        assert tracer.current_step_id is None

    def test_trace_id_accessible(self):
        """Test trace ID is accessible via context."""
        tracer = ExecutionTracer(trace_id="trace_id_test")

        tracer.start_trace()

        assert tracer.current_trace_id == "trace_id_test"

        tracer.end_trace()
        assert tracer.current_trace_id is None

    def test_hierarchical_parent_tracking(self):
        """Test parent_step_id is set correctly."""
        tracer = ExecutionTracer(trace_id="parent_test")

        step1 = tracer.start_step(name="root", step_type=StepType.NODE_START)
        step2 = tracer.start_step(name="child", step_type=StepType.NODE_START, parent_step_id=step1)

        step = tracer.trace.steps[step2]
        assert step.parent_id == step1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
