"""Tests for UniversalSolver module."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.agent.core.evolution.universal_solver import (
    UniversalSolver,
    SolverResult,
    SolverStatus,
)


class TestSolverResult:
    """Tests for SolverResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = SolverResult(
            task="Test task",
            status=SolverStatus.SUCCESS,
            solution="Output",
            commands=["cmd1", "cmd2"],
            outputs=["output1", "output2"],
            duration_ms=100.0,
        )

        assert result.task == "Test task"
        assert result.status == SolverStatus.SUCCESS
        assert result.solution == "Output"
        assert len(result.commands) == 2
        assert result.duration_ms == 100.0
        assert result.trace_id is None
        assert result.error is None

    def test_create_failed_result(self):
        """Test creating a failed result."""
        result = SolverResult(
            task="Failing task",
            status=SolverStatus.FAILED,
            solution=None,
            commands=["failing_cmd"],
            outputs=["error output"],
            duration_ms=50.0,
            error="Command not found",
        )

        assert result.status == SolverStatus.FAILED
        assert result.error == "Command not found"

    def test_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        result = SolverResult(
            task="Test",
            status=SolverStatus.SUCCESS,
            solution="sol",
            commands=[],
            outputs=[],
            duration_ms=0,
        )

        assert result.metadata == {}

    def test_custom_metadata(self):
        """Test custom metadata."""
        result = SolverResult(
            task="Test",
            status=SolverStatus.SUCCESS,
            solution="sol",
            commands=[],
            outputs=[],
            duration_ms=0,
            metadata={"key": "value"},
        )

        assert result.metadata == {"key": "value"}


class TestSolverStatus:
    """Tests for SolverStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert SolverStatus.SUCCESS == "success"
        assert SolverStatus.FAILED == "failed"
        assert SolverStatus.PARTIAL == "partial"
        assert SolverStatus.SKIPPED == "skipped"


class TestUniversalSolver:
    """Tests for UniversalSolver class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock trace collector."""
        tracer = AsyncMock()
        tracer.record = AsyncMock(return_value="trace_123")
        tracer.get_traces_by_task = AsyncMock(return_value=[])
        tracer.get_recent_traces = AsyncMock(return_value=[])
        return tracer

    @pytest.fixture
    def solver(self, mock_tracer):
        """Create a solver with mock tracer."""
        return UniversalSolver(trace_collector=mock_tracer)

    @pytest.mark.asyncio
    async def test_solve_with_mocked_omni_cell(self, solver, mock_tracer):
        """Test solve with mocked OmniCell."""
        with patch.object(solver, "_get_omni_cell", new_callable=AsyncMock) as mock_cell:
            mock_omni = AsyncMock()
            mock_omni.execute = AsyncMock(return_value="test output")
            mock_cell.return_value = mock_omni

            result = await solver.solve("list files")

            assert result.status == SolverStatus.SUCCESS
            assert result.task == "list files"
            assert len(result.commands) == 1
            assert result.trace_id == "trace_123"
            mock_tracer.record.assert_called_once()

    @pytest.mark.asyncio
    async def test_solve_without_trace_recording(self, solver, mock_tracer):
        """Test solve without recording trace."""
        with patch.object(solver, "_get_omni_cell", new_callable=AsyncMock) as mock_cell:
            mock_omni = AsyncMock()
            mock_omni.execute = AsyncMock(return_value="output")
            mock_cell.return_value = mock_omni

            result = await solver.solve("test task", record_trace=False)

            assert result.status == SolverStatus.SUCCESS
            assert result.trace_id is None
            mock_tracer.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_solve_execution_failure(self, solver, mock_tracer):
        """Test solve when execution fails."""
        with patch.object(solver, "_get_omni_cell", new_callable=AsyncMock) as mock_cell:
            mock_omni = AsyncMock()
            mock_omni.execute = AsyncMock(side_effect=Exception("Command failed"))
            mock_cell.return_value = mock_omni

            result = await solver.solve("failing task")

            assert result.status == SolverStatus.FAILED
            assert "Command failed" in result.error
            assert result.trace_id is None

    @pytest.mark.asyncio
    async def test_task_pattern_extraction(self, solver):
        """Test pattern extraction from task description."""
        # Test file pattern extraction - captures *.py
        result = solver._extract_pattern("find *.py files")
        assert result == "*.py"

        # This also returns *.py since the regex looks for * followed by optional . and word chars
        result = solver._extract_pattern("list test_*.py")
        assert result == "*.py"

    @pytest.mark.asyncio
    async def test_commit_message_extraction(self, solver):
        """Test commit message extraction."""
        result = solver._extract_commit_message("git commit: update documentation")
        assert result == "update documentation"

        result = solver._extract_commit_message("commit: fix bug in login")
        assert result == "fix bug in login"

    @pytest.mark.asyncio
    async def test_task_id_generation(self, solver):
        """Test task ID generation."""
        id1 = solver._generate_task_id("test task")
        id2 = solver._generate_task_id("test task")

        # Same task should produce different IDs (due to timestamp)
        assert id1.startswith("task_")
        assert len(id1) == 13  # "task_" + 8 char hash

    @pytest.mark.asyncio
    async def test_execution_history(self, solver, mock_tracer):
        """Test getting execution history."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        mock_traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="list files",
                commands=["ls"],
                outputs=["file1.txt"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t2",
                task_description="find files",
                commands=["find . -name *.py"],
                outputs=["test.py"],
                success=True,
                duration_ms=20.0,
                timestamp=datetime.now(),
            ),
        ]
        mock_tracer.get_recent_traces = AsyncMock(return_value=mock_traces)

        history = await solver.get_execution_history()

        assert len(history) == 2
        assert history[0].status == SolverStatus.SUCCESS
        assert history[1].commands == ["find . -name *.py"]

    @pytest.mark.asyncio
    async def test_execution_history_with_pattern(self, solver, mock_tracer):
        """Test getting execution history with pattern filter."""
        mock_tracer.get_traces_by_task = AsyncMock(return_value=[])

        await solver.get_execution_history(task_pattern="list")

        mock_tracer.get_traces_by_task.assert_called_once_with("list")

    @pytest.mark.asyncio
    async def test_record_failure(self, solver, mock_tracer):
        """Test recording a failed execution."""
        trace_id = await solver.record_failure(
            task="failed task",
            commands=["bad_cmd"],
            outputs=["error"],
            error="Command not found",
        )

        assert trace_id == "trace_123"
        mock_tracer.record.assert_called_once()
        call_kwargs = mock_tracer.record.call_args[1]
        assert call_kwargs["success"] is False
        assert "error_type" in call_kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_lazy_tracer_initialization(self):
        """Test that tracer is lazily initialized."""
        solver = UniversalSolver(trace_collector=None)

        with patch.object(solver, "_get_omni_cell", new_callable=AsyncMock) as mock_cell:
            mock_omni = AsyncMock()
            mock_omni.execute = AsyncMock(side_effect=Exception("No omni"))
            mock_cell.return_value = mock_omni

            # This should not raise - tracer is fetched lazily
            result = await solver.solve("test", record_trace=False)
            assert result.status == SolverStatus.FAILED


class TestUniversalSolverPlanning:
    """Tests for execution planning in UniversalSolver."""

    @pytest.fixture
    def solver(self):
        """Create solver without tracer."""
        return UniversalSolver(trace_collector=None)

    @pytest.mark.asyncio
    async def test_plan_list_files(self, solver):
        """Test planning for list files task."""
        plan = await solver._plan_execution("list all files in current directory")
        assert plan == ["ls -la"]

    @pytest.mark.asyncio
    async def test_plan_find_files(self, solver):
        """Test planning for find files task."""
        plan = await solver._plan_execution("find *.py files")
        assert plan == ["find . -name '*.py' -type f"]

    @pytest.mark.asyncio
    async def test_plan_git_status(self, solver):
        """Test planning for git status task."""
        plan = await solver._plan_execution("git status")
        assert plan == ["git status"]

    @pytest.mark.asyncio
    async def test_plan_git_commit(self, solver):
        """Test planning for git commit task."""
        plan = await solver._plan_execution("git commit: update documentation")
        assert plan == ["git add -A", 'git commit -m "update documentation"']

    @pytest.mark.asyncio
    async def test_plan_default_shell(self, solver):
        """Test default planning falls back to shell command."""
        plan = await solver._plan_execution("echo hello world")
        assert plan == ["echo hello world"]

    @pytest.mark.asyncio
    async def test_plan_pytest(self, solver):
        """Test planning for pytest."""
        plan = await solver._plan_execution("run python tests")
        assert plan == ["python -m pytest -v"]
