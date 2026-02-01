"""Tests for evolution tracer module."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from omni.agent.core.evolution.tracer import ExecutionTrace, TraceCollector


class TestExecutionTrace:
    """Tests for ExecutionTrace dataclass."""

    def test_create_trace(self):
        """Test creating an execution trace."""
        trace = ExecutionTrace(
            task_id="test_task",
            task_description="Rename files",
            commands=["ls *.txt", "for f in *.txt; do mv $f ${f%.txt}.md; done"],
            outputs=["file1.txt", "file2.txt", "2 files renamed"],
            success=True,
            duration_ms=150.5,
        )

        assert trace.task_id == "test_task"
        assert trace.task_description == "Rename files"
        assert len(trace.commands) == 2
        assert trace.success is True
        assert trace.duration_ms == 150.5
        assert isinstance(trace.timestamp, datetime)

    def test_trace_to_dict(self):
        """Test serialization to dictionary."""
        trace = ExecutionTrace(
            task_id="test_task",
            task_description="Test task",
            commands=["cmd1", "cmd2"],
            outputs=["output1"],
            success=True,
            duration_ms=100.0,
            metadata={"key": "value"},
        )

        data = trace.to_dict()

        assert data["task_id"] == "test_task"
        assert data["task_description"] == "Test task"
        assert data["commands"] == ["cmd1", "cmd2"]
        assert data["success"] is True
        assert data["metadata"] == {"key": "value"}

    def test_trace_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "task_id": "test_task",
            "task_description": "Test task",
            "commands": ["cmd1"],
            "outputs": ["output1"],
            "success": False,
            "duration_ms": 50.0,
            "timestamp": "2026-01-30T12:00:00",
            "metadata": {"error": "test error"},
        }

        trace = ExecutionTrace.from_dict(data)

        assert trace.task_id == "test_task"
        assert trace.success is False
        assert trace.metadata == {"error": "test error"}
        assert trace.timestamp == datetime(2026, 1, 30, 12, 0, 0)

    def test_trace_roundtrip(self):
        """Test serialization roundtrip."""
        original = ExecutionTrace(
            task_id="roundtrip_test",
            task_description="Roundtrip test",
            commands=["echo hello"],
            outputs=["hello"],
            success=True,
            duration_ms=25.0,
        )

        serialized = original.to_dict()
        restored = ExecutionTrace.from_dict(serialized)

        assert restored.task_id == original.task_id
        assert restored.task_description == original.task_description
        assert restored.commands == original.commands
        assert restored.success == original.success


class TestTraceCollector:
    """Tests for TraceCollector."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for traces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def collector(self, temp_dir):
        """Create a trace collector with temp directory."""
        return TraceCollector(trace_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_record_trace(self, collector, temp_dir):
        """Test recording a trace."""
        trace_id = await collector.record(
            task_id="test_task",
            task_description="Test description",
            commands=["ls", "cat"],
            outputs=["file1.txt", "content"],
            success=True,
            duration_ms=100.0,
        )

        assert trace_id is not None
        assert temp_dir.exists()

        # Check trace file was created
        trace_files = list(temp_dir.glob("*.json"))
        assert len(trace_files) == 1

    @pytest.mark.asyncio
    async def test_get_trace(self, collector):
        """Test retrieving a trace."""
        # Record a trace
        trace_id = await collector.record(
            task_id="get_test",
            task_description="Get test task",
            commands=["echo test"],
            outputs=["test output"],
            success=True,
            duration_ms=50.0,
        )

        # Retrieve it
        trace = await collector.get_trace(trace_id)

        assert trace is not None
        assert trace.task_id == "get_test"
        assert trace.task_description == "Get test task"

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace(self, collector):
        """Test getting a trace that doesn't exist."""
        trace = await collector.get_trace("nonexistent_trace_id")
        assert trace is None

    @pytest.mark.asyncio
    async def test_get_traces_by_task(self, collector):
        """Test filtering traces by task pattern."""
        # Record multiple traces
        await collector.record(
            task_id="task_1",
            task_description="Rename files task",
            commands=["mv *.txt *.md"],
            outputs=["done"],
            success=True,
            duration_ms=100.0,
        )

        await collector.record(
            task_id="task_2",
            task_description="Another rename task",
            commands=["mv *.py *.bak"],
            outputs=["done"],
            success=True,
            duration_ms=80.0,
        )

        await collector.record(
            task_id="task_3",
            task_description="Delete files task",
            commands=["rm *.tmp"],
            outputs=["done"],
            success=True,
            duration_ms=50.0,
        )

        # Filter by "rename" pattern
        rename_traces = await collector.get_traces_by_task("rename")
        assert len(rename_traces) == 2

        # Filter by "delete" pattern
        delete_traces = await collector.get_traces_by_task("delete")
        assert len(delete_traces) == 1

    @pytest.mark.asyncio
    async def test_get_recent_traces(self, collector):
        """Test getting recent traces with limit."""
        # Record multiple traces
        for i in range(5):
            await collector.record(
                task_id=f"task_{i}",
                task_description=f"Task {i}",
                commands=[f"cmd{i}"],
                outputs=[f"out{i}"],
                success=True,
                duration_ms=10.0,
            )

        # Get recent with limit
        recent = await collector.get_recent_traces(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_cleanup_old_traces(self, collector):
        """Test cleaning up old traces."""
        # Create more traces than keep_count
        for i in range(10):
            await collector.record(
                task_id=f"cleanup_task_{i}",
                task_description=f"Task {i}",
                commands=["cmd"],
                outputs=["out"],
                success=True,
                duration_ms=10.0,
            )

        initial_count = collector.trace_count
        assert initial_count == 10

        # Cleanup keeping only 5
        removed = await collector.cleanup_old_traces(keep_count=5)

        assert removed == 5
        assert collector.trace_count == 5

    @pytest.mark.asyncio
    async def test_get_traces_for_harvester(self, collector):
        """Test getting traces formatted for harvester."""
        await collector.record(
            task_id="harvest_test",
            task_description="Test for harvester",
            commands=["cmd1", "cmd2"],
            outputs=["out1", "out2"],
            success=True,
            duration_ms=100.0,
        )

        traces = await collector.get_traces_for_harvester()

        assert len(traces) == 1
        assert "commands" in traces[0]
        assert "outputs" in traces[0]
        assert "success" in traces[0]
        # Task description should NOT be at top level (harvester expects formatted data)
        assert traces[0]["task_description"] == "Test for harvester"

    @pytest.mark.asyncio
    async def test_record_with_metadata(self, collector):
        """Test recording a trace with additional metadata."""
        trace_id = await collector.record(
            task_id="meta_test",
            task_description="Metadata test",
            commands=["echo test"],
            outputs=["test"],
            success=True,
            duration_ms=50.0,
            metadata={"session_id": "sess_123", "user": "test_user"},
        )

        trace = await collector.get_trace(trace_id)

        assert trace is not None
        assert trace.metadata.get("session_id") == "sess_123"
        assert trace.metadata.get("user") == "test_user"

    @pytest.mark.asyncio
    async def test_failed_execution_trace(self, collector):
        """Test recording a failed execution trace."""
        trace_id = await collector.record(
            task_id="failed_task",
            task_description="This task failed",
            commands=["failing_cmd"],
            outputs=["error: command not found"],
            success=False,
            duration_ms=25.0,
        )

        trace = await collector.get_trace(trace_id)

        assert trace is not None
        assert trace.success is False
        assert "error" in trace.outputs[0].lower()
