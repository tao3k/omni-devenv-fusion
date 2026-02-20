"""Tests for Harvester module - trace-based skill extraction."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from omni.agent.core.evolution.harvester import (
    process_trace_for_skill,
    _heuristic_extract,
)
from omni.agent.core.evolution.schemas import CandidateSkill
from omni.agent.core.evolution.tracer import ExecutionTrace


class TestProcessTraceForSkill:
    """Tests for process_trace_for_skill function."""

    @pytest.fixture
    def sample_trace(self):
        """Create sample execution trace."""
        return ExecutionTrace(
            task_id="trace_123",
            task_description="Rename all .txt files to .md",
            commands=[
                "ls *.txt",
                "for f in *.txt; do mv $f ${f%.txt}.md; done",
            ],
            outputs=["file1.txt file2.txt", "2 files renamed"],
            success=True,
            duration_ms=150.0,
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_process_trace_without_llm(self, sample_trace):
        """Test processing trace with heuristic extraction (no LLM)."""
        result = await process_trace_for_skill(sample_trace, llm=None)

        assert result is not None
        assert isinstance(result, CandidateSkill)
        assert "rename" in result.suggested_name.lower()
        assert result.category == "automation"

    @pytest.mark.asyncio
    async def test_process_failed_trace(self, sample_trace):
        """Test that failed traces are skipped."""
        sample_trace = ExecutionTrace(
            task_id="failed_task",
            task_description="Failed operation",
            commands=["failing_cmd"],
            outputs=["error: command not found"],
            success=False,
            duration_ms=50.0,
            timestamp=datetime.now(),
        )

        result = await process_trace_for_skill(sample_trace, llm=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_trivial_trace(self):
        """Test that trivial traces are skipped."""
        trace = ExecutionTrace(
            task_id="trivial",
            task_description="Simple command",
            commands=["ls"],
            outputs=["file1"],
            success=True,
            duration_ms=50.0,  # Below 100ms threshold
            timestamp=datetime.now(),
        )

        result = await process_trace_for_skill(trace, llm=None)

        assert result is None  # Should be skipped due to low duration

    @pytest.mark.asyncio
    async def test_process_empty_commands(self):
        """Test handling of trace with no commands."""
        trace = ExecutionTrace(
            task_id="empty",
            task_description="No commands",
            commands=[],
            outputs=["nothing"],
            success=True,
            duration_ms=0,
            timestamp=datetime.now(),
        )

        result = await process_trace_for_skill(trace, llm=None)

        assert result is None


class TestHeuristicExtract:
    """Tests for _heuristic_extract fallback function."""

    def test_heuristic_extract_file_pattern(self):
        """Test heuristic extraction with file patterns."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Find all Python files",
            commands=["find *.py -type f"],
            outputs=["test.py main.py"],
            success=True,
            duration_ms=100.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is not None
        assert "pattern" in result.parameters
        assert result.category == "automation"

    def test_heuristic_extract_git_commit(self):
        """Test heuristic extraction with git commit."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Commit changes",
            commands=["git add -A", 'git commit -m "update"'],
            outputs=["[main abc123] update"],
            success=True,
            duration_ms=200.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is not None
        assert "message" in result.parameters
        # No 'branch' because there's no 'git push' in the trace

    def test_heuristic_extract_file_rename(self):
        """Test heuristic extraction with file rename (mv)."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Rename files",
            commands=["mv *.txt *.md"],
            outputs=["done"],
            success=True,
            duration_ms=150.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is not None
        assert "source" in result.parameters
        assert "dest" in result.parameters

    def test_heuristic_extract_complex_trace(self):
        """Test heuristic extraction with complex multi-command trace."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Complex task",
            commands=["git status", "git add -A", 'git commit -m "test"'],
            outputs=["clean", "done"],
            success=True,
            duration_ms=300.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is not None
        # Should have parameters from multiple commands
        assert len(result.parameters) > 0
        assert result.nushell_script == trace.commands[0]  # Uses first command

    def test_heuristic_extract_empty_commands(self):
        """Test heuristic extraction with empty commands."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Empty",
            commands=[],
            outputs=[],
            success=True,
            duration_ms=100.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is None

    def test_heuristic_extract_confidence(self):
        """Test that heuristic extraction has lower confidence."""
        trace = ExecutionTrace(
            task_id="test",
            task_description="Test task",
            commands=["echo test"],
            outputs=["test"],
            success=True,
            duration_ms=100.0,
            timestamp=datetime.now(),
        )

        result = _heuristic_extract(trace)

        assert result is not None
        assert result.confidence_score == 0.5
        assert "Heuristic extraction" in result.reasoning


class TestHarvesterClass:
    """Tests for Harvester class."""

    @pytest.mark.asyncio
    async def test_harvester_init_without_llm(self):
        """Test initializing harvester without LLM."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester(llm=None)
        assert harvester.llm is None

    @pytest.mark.asyncio
    async def test_harvester_init_with_llm(self):
        """Test initializing harvester with LLM."""
        from omni.agent.core.evolution.harvester import Harvester

        mock_llm = AsyncMock()
        harvester = Harvester(llm=mock_llm)
        assert harvester.llm is mock_llm

    def test_harvester_init_with_engine(self):
        """Test initializing harvester with engine (OmniLoop integration)."""
        from omni.agent.core.evolution.harvester import Harvester

        mock_engine = object()
        harvester = Harvester(engine=mock_engine)
        assert harvester._engine is mock_engine
        assert harvester.llm is None


class TestHarvesterInterface:
    """Contract tests: Harvester must have methods expected by OmniLoop._trigger_harvester.

    Prevents regression when Harvester API changes without updating loop integration.
    """

    def test_harvester_has_analyze_session(self):
        """Harvester must have analyze_session method for OmniLoop evolution cycle."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester()
        assert hasattr(harvester, "analyze_session")
        assert callable(getattr(harvester, "analyze_session"))

    def test_harvester_has_extract_lessons(self):
        """Harvester must have extract_lessons method for OmniLoop evolution cycle."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester()
        assert hasattr(harvester, "extract_lessons")
        assert callable(getattr(harvester, "extract_lessons"))

    @pytest.mark.asyncio
    async def test_analyze_session_callable_with_history(self):
        """analyze_session must accept list[dict] and return CandidateSkill | None."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester(llm=None)
        result = await harvester.analyze_session([])
        assert result is None

        result = await harvester.analyze_session(
            [
                {"role": "user", "content": "test"},
                {"role": "assistant", "content": "ok"},
            ]
        )
        # No tool_calls in history -> returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_session_with_tool_calls(self):
        """analyze_session extracts commands from tool_calls and may return CandidateSkill."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester(llm=None)
        history = [
            {"role": "user", "content": "Rename all txt files to md"},
            {
                "role": "assistant",
                "content": "I'll do that",
                "tool_calls": [
                    {"function": {"name": "skill.batch_rename", "arguments": "{}"}},
                ],
            },
        ]
        result = await harvester.analyze_session(history)
        # With commands, heuristic may return CandidateSkill
        assert result is None or isinstance(result, CandidateSkill)

    @pytest.mark.asyncio
    async def test_extract_lessons_callable_returns_none_or_lesson(self):
        """extract_lessons must accept list[dict] and not raise."""
        from omni.agent.core.evolution.harvester import Harvester

        harvester = Harvester()
        result = await harvester.extract_lessons([])
        assert result is None

        result = await harvester.extract_lessons(
            [
                {"role": "user", "content": "task"},
                {"role": "assistant", "content": "done"},
            ]
        )
        assert result is None  # Stub returns None
