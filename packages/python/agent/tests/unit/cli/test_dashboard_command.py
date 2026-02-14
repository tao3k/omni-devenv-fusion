"""Unit tests for dashboard command and session metrics persistence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app
from omni.agent.cli.session_metrics import read_session_metrics, write_session_metrics


class TestSessionMetrics:
    """Tests for session_metrics read/write."""

    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """Write then read returns the same data plus timestamp."""
        with patch("omni.agent.cli.session_metrics.get_cache_dir", return_value=tmp_path):
            write_session_metrics(
                {
                    "task": "test task",
                    "session_id": "s1",
                    "step_count": 3,
                    "tool_calls": 2,
                }
            )
            data = read_session_metrics()
        assert data is not None
        assert data["task"] == "test task"
        assert data["session_id"] == "s1"
        assert data["step_count"] == 3
        assert data["tool_calls"] == 2
        assert "timestamp" in data

    def test_read_missing_returns_none(self, tmp_path: Path) -> None:
        """When file does not exist, read returns None."""
        with patch("omni.agent.cli.session_metrics.get_cache_dir", return_value=tmp_path):
            out = read_session_metrics()
        assert out is None

    def test_write_adds_timestamp_if_absent(self, tmp_path: Path) -> None:
        """write_session_metrics adds timestamp when not provided."""
        with patch("omni.agent.cli.session_metrics.get_cache_dir", return_value=tmp_path):
            write_session_metrics({"task": "x"})
            data = read_session_metrics()
        assert data is not None
        assert "timestamp" in data


class TestDashboardCommand:
    """Tests for `omni dashboard` CLI."""

    def test_dashboard_no_metrics_exits_0(self, tmp_path: Path) -> None:
        """When no session metrics exist, dashboard prints message and exits 0."""
        with patch("omni.agent.cli.commands.dashboard.read_session_metrics", return_value=None):
            runner = CliRunner()
            result = runner.invoke(app, ["dashboard"])
        assert result.exit_code == 0
        assert "No session metrics" in result.output
        assert "omni run" in result.output

    def test_dashboard_with_metrics_prints_table(self, tmp_path: Path) -> None:
        """When metrics exist, dashboard prints a table with task and steps."""
        with patch(
            "omni.agent.cli.commands.dashboard.read_session_metrics",
            return_value={
                "task": "list files",
                "session_id": "sid-1",
                "step_count": 2,
                "tool_calls": 1,
                "est_tokens": 500,
                "timestamp": "2025-01-01T00:00:00Z",
            },
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["dashboard"])
        assert result.exit_code == 0
        assert "list files" in result.output
        assert "sid-1" in result.output
        assert "2" in result.output
        assert "500" in result.output
