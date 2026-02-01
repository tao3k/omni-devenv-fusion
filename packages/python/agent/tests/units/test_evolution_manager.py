"""Tests for EvolutionManager module."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.agent.core.evolution.manager import (
    EvolutionManager,
    EvolutionConfig,
    EvolutionState,
    CrystallizationCandidate,
)


class TestEvolutionConfig:
    """Tests for EvolutionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EvolutionConfig()

        assert config.min_trace_frequency == 3
        assert config.min_success_rate == 0.8
        assert config.max_trace_age_hours == 24
        assert config.check_interval_seconds == 300
        assert config.batch_size == 10
        assert config.auto_crystallize is False
        assert config.dry_run is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = EvolutionConfig(
            min_trace_frequency=5,
            min_success_rate=0.9,
            auto_crystallize=True,
            dry_run=True,
        )

        assert config.min_trace_frequency == 5
        assert config.min_success_rate == 0.9
        assert config.auto_crystallize is True
        assert config.dry_run is True


class TestEvolutionState:
    """Tests for EvolutionState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = EvolutionState()

        assert state.last_check is None
        assert state.total_traces == 0
        assert state.total_skills_crystallized == 0
        assert state.pending_candidates == 0
        assert state.last_error is None
        assert state.is_active is False

    def test_custom_state(self):
        """Test custom state values."""
        now = datetime.now()
        state = EvolutionState(
            last_check=now,
            total_traces=100,
            total_skills_crystallized=5,
            pending_candidates=3,
            last_error="Previous error",
            is_active=True,
        )

        assert state.last_check == now
        assert state.total_traces == 100
        assert state.total_skills_crystallized == 5


class TestCrystallizationCandidate:
    """Tests for CrystallizationCandidate dataclass."""

    def test_create_candidate(self):
        """Test creating a candidate."""
        candidate = CrystallizationCandidate(
            task_pattern="list files",
            trace_count=5,
            success_rate=0.9,
            avg_duration_ms=50.0,
            command_pattern=["ls", "ls -la"],
            sample_traces=["trace1", "trace2"],
        )

        assert candidate.task_pattern == "list files"
        assert candidate.trace_count == 5
        assert candidate.success_rate == 0.9
        assert candidate.avg_duration_ms == 50.0
        assert len(candidate.command_pattern) == 2

    def test_candidate_default_timestamp(self):
        """Test that created_at defaults to now."""
        before = datetime.now()
        candidate = CrystallizationCandidate(
            task_pattern="test",
            trace_count=3,
            success_rate=1.0,
            avg_duration_ms=10.0,
            command_pattern=[],
            sample_traces=[],
        )
        after = datetime.now()

        assert before <= candidate.created_at <= after


class TestEvolutionManager:
    """Tests for EvolutionManager class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock trace collector."""
        tracer = AsyncMock()
        tracer.get_recent_traces = AsyncMock(return_value=[])
        tracer.get_traces_by_task = AsyncMock(return_value=[])
        tracer.cleanup_old_traces = AsyncMock(return_value=0)
        tracer.trace_count = 0
        return tracer

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return EvolutionConfig(
            min_trace_frequency=2,
            min_success_rate=0.7,
            check_interval_seconds=60,
        )

    @pytest.fixture
    def manager(self, config, mock_tracer):
        """Create manager with mocks."""
        return EvolutionManager(
            config=config,
            trace_collector=mock_tracer,
        )

    @pytest.mark.asyncio
    async def test_check_crystallization_no_traces(self, manager, mock_tracer):
        """Test checking when no traces exist."""
        mock_tracer.get_recent_traces = AsyncMock(return_value=[])

        candidates = await manager.check_crystallization()

        assert candidates == []
        assert manager.state.is_active is True

    @pytest.mark.asyncio
    async def test_check_crystallization_below_threshold(self, manager, mock_tracer):
        """Test checking when traces are below threshold."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        # Only 1 trace, threshold is 2
        mock_traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="list files",
                commands=["ls"],
                outputs=["file1"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
        ]
        mock_tracer.get_recent_traces = AsyncMock(return_value=mock_traces)

        candidates = await manager.check_crystallization()

        assert candidates == []
        assert manager.state.pending_candidates == 0

    @pytest.mark.asyncio
    async def test_check_crystallization_candidate_found(self, manager, mock_tracer):
        """Test when candidate meets crystallization criteria."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        # 3 traces (threshold), 100% success rate (threshold 0.7)
        mock_traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="list files",
                commands=["ls"],
                outputs=["file1"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t2",
                task_description="list files",
                commands=["ls"],
                outputs=["file1", "file2"],
                success=True,
                duration_ms=12.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t3",
                task_description="list files",
                commands=["ls"],
                outputs=["file1", "file2", "file3"],
                success=True,
                duration_ms=11.0,
                timestamp=datetime.now(),
            ),
        ]
        mock_tracer.get_recent_traces = AsyncMock(return_value=mock_traces)

        candidates = await manager.check_crystallization()

        assert len(candidates) == 1
        assert candidates[0].task_pattern == "list files"
        assert candidates[0].trace_count == 3
        assert candidates[0].success_rate == 1.0

    @pytest.mark.asyncio
    async def test_check_crystallization_low_success_rate(self, manager, mock_tracer):
        """Test candidate not found when success rate is too low."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        # 3 traces but only 67% success rate (threshold 0.7)
        mock_traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="task",
                commands=["cmd"],
                outputs=["out"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t2",
                task_description="task",
                commands=["cmd"],
                outputs=["error"],
                success=False,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t3",
                task_description="task",
                commands=["cmd"],
                outputs=["error"],
                success=False,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
        ]
        mock_tracer.get_recent_traces = AsyncMock(return_value=mock_traces)

        candidates = await manager.check_crystallization()

        assert len(candidates) == 0  # Should not be a candidate

    @pytest.mark.asyncio
    async def test_crystallize_candidate_dry_run(self, manager):
        """Test dry run mode for crystallization."""
        candidate = CrystallizationCandidate(
            task_pattern="list files",
            trace_count=5,
            success_rate=1.0,
            avg_duration_ms=10.0,
            command_pattern=["ls"],
            sample_traces=["t1", "t2"],
        )

        manager.config.dry_run = True

        result = await manager.crystallize_candidate(candidate)

        assert result["status"] == "dry_run"
        assert result["candidate"] == "list files"

    @pytest.mark.asyncio
    async def test_run_evolution_cycle(self, manager, mock_tracer):
        """Test running a complete evolution cycle."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        mock_tracer.get_recent_traces = AsyncMock(return_value=[])
        manager.config.dry_run = True

        result = await manager.run_evolution_cycle()

        assert "cycle_started" in result
        assert "cycle_completed" in result
        assert "duration_ms" in result
        assert result["candidates_found"] == 0

    @pytest.mark.asyncio
    async def test_get_evolution_status(self, manager, mock_tracer):
        """Test getting evolution status."""
        mock_tracer.trace_count = 42

        status = await manager.get_evolution_status()

        assert "state" in status
        assert "config" in status
        assert status["trace_count"] == 42
        assert status["state"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_cleanup_old_traces(self, manager, mock_tracer):
        """Test cleaning up old traces."""
        mock_tracer.cleanup_old_traces = AsyncMock(return_value=10)

        removed = await manager.cleanup_old_traces(keep_count=100)

        assert removed == 10
        mock_tracer.cleanup_old_traces.assert_called_once_with(100)


class TestEvolutionManagerGrouping:
    """Tests for trace grouping logic in EvolutionManager."""

    @pytest.fixture
    def manager(self):
        """Create manager with defaults."""
        return EvolutionManager()

    def test_group_traces_by_task(self, manager):
        """Test grouping traces by task description."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="List Files",
                commands=["ls"],
                outputs=["file1"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t2",
                task_description="list files",  # Lowercase
                commands=["ls"],
                outputs=["file2"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t3",
                task_description="Find Files",
                commands=["find"],
                outputs=["file3"],
                success=True,
                duration_ms=20.0,
                timestamp=datetime.now(),
            ),
        ]

        groups = manager._group_traces_by_task(traces)

        # Should normalize case
        assert "list files" in groups
        assert len(groups["list files"]) == 2
        assert "find files" in groups
        assert len(groups["find files"]) == 1

    def test_extract_command_pattern(self, manager):
        """Test extracting command patterns from traces."""
        from omni.agent.core.evolution.tracer import ExecutionTrace

        traces = [
            ExecutionTrace(
                task_id="t1",
                task_description="list",
                commands=["ls", "ls -la"],
                outputs=["out"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
            ExecutionTrace(
                task_id="t2",
                task_description="list",
                commands=["ls", "pwd"],
                outputs=["out"],
                success=True,
                duration_ms=10.0,
                timestamp=datetime.now(),
            ),
        ]

        pattern = manager._extract_command_pattern(traces)

        # Should preserve order and uniqueness
        assert "ls" in pattern
        assert "ls -la" in pattern
        assert "pwd" in pattern


class TestEvolutionManagerIntegration:
    """Integration tests for EvolutionManager with real-ish components."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_manager_with_real_tracer(self, temp_dir):
        """Test manager with real TraceCollector."""
        from omni.agent.core.evolution.tracer import TraceCollector
        from omni.agent.core.evolution.manager import EvolutionManager

        tracer = TraceCollector(trace_dir=temp_dir)
        manager = EvolutionManager(trace_collector=tracer)

        # Record some traces
        for i in range(5):
            await tracer.record(
                task_id=f"task_{i}",
                task_description="list files task",
                commands=["ls"],
                outputs=[f"file{i}"],
                success=True,
                duration_ms=10.0,
            )

        # Check crystallization
        candidates = await manager.check_crystallization()

        assert len(candidates) == 1
        assert candidates[0].trace_count == 5
        assert manager.state.total_traces == 5

        # Cleanup
        removed = await manager.cleanup_old_traces(keep_count=2)
        assert removed == 3


class TestQuarantineManagement:
    """Tests for quarantine management and Immune System integration."""

    @pytest.fixture
    def quarantine_dir(self, tmp_path):
        """Create quarantine directory with test skills."""
        quarantine = tmp_path / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)

        # Create simple test skills (names not starting with 'test_' to avoid filtering)
        skill_content = '''
"""Sample quarantine skill."""

async def sample_quarantine_skill():
    """A sample skill in quarantine."""
    return {"success": True}
'''
        (quarantine / "sample_quarantine_skill.py").write_text(skill_content)

        # Create another skill
        skill2_content = '''
"""Another quarantine skill."""

def another_quarantine_skill():
    """Another sample skill."""
    return "done"
'''
        (quarantine / "another_quarantine_skill.py").write_text(skill2_content)

        return quarantine

    @pytest.mark.asyncio
    async def test_scan_quarantine_empty(self):
        """Test scanning empty quarantine directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EvolutionManager()
            manager._immune_system = AsyncMock()
            manager._immune_system.process_candidate = AsyncMock(
                return_value=MagicMock(promoted=True, rejection_reason=None)
            )

            results = await manager.scan_quarantine(str(Path(tmpdir) / "empty_quarantine"))

            assert results == []

    @pytest.mark.asyncio
    async def test_scan_quarantine_with_skills(self, quarantine_dir):
        """Test scanning quarantine with skills."""
        manager = EvolutionManager()
        manager._immune_system = AsyncMock()

        # Mock immune report
        immune_report = MagicMock()
        immune_report.promoted = True
        immune_report.rejection_reason = None
        immune_report.to_dict.return_value = {"skill_name": "test"}
        manager._immune_system.process_candidate = AsyncMock(return_value=immune_report)

        results = await manager.scan_quarantine(str(quarantine_dir))

        assert len(results) == 2
        assert all(r["promoted"] for r in results)

    @pytest.mark.asyncio
    async def test_scan_quarantine_rejected(self, quarantine_dir):
        """Test scanning quarantine with rejected skills."""
        manager = EvolutionManager()
        manager._immune_system = AsyncMock()

        # Mock rejected immune report
        immune_report = MagicMock()
        immune_report.promoted = False
        immune_report.rejection_reason = "Security violation"
        immune_report.to_dict.return_value = {"skill_name": "test"}
        manager._immune_system.process_candidate = AsyncMock(return_value=immune_report)

        results = await manager.scan_quarantine(str(quarantine_dir))

        assert len(results) == 2
        assert all(not r["promoted"] for r in results)
        assert "Security violation" in results[0]["reason"]

    @pytest.mark.asyncio
    async def test_promote_skill_success(self, quarantine_dir):
        """Test promoting a quarantined skill."""
        manager = EvolutionManager()
        manager._immune_system = AsyncMock()

        immune_report = MagicMock()
        immune_report.promoted = True
        immune_report.rejection_reason = None
        immune_report.to_dict.return_value = {"promoted": True}
        manager._immune_system.process_candidate = AsyncMock(return_value=immune_report)

        skill_path = str(quarantine_dir / "test_skill.py")
        result = await manager.promote_skill(skill_path)

        assert result["promoted"] is True
        assert result["skill_path"] == skill_path

    @pytest.mark.asyncio
    async def test_promote_skill_rejected(self, quarantine_dir):
        """Test promoting a rejected skill."""
        manager = EvolutionManager()
        manager._immune_system = AsyncMock()

        immune_report = MagicMock()
        immune_report.promoted = False
        immune_report.rejection_reason = "Dangerous pattern detected"
        immune_report.to_dict.return_value = {"rejected": True}
        manager._immune_system.process_candidate = AsyncMock(return_value=immune_report)

        skill_path = str(quarantine_dir / "test_skill.py")
        result = await manager.promote_skill(skill_path)

        assert result["promoted"] is False
        assert result["reason"] == "Dangerous pattern detected"
