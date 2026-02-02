"""Unit tests for sync and reindex commands."""

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, AsyncMock
from omni.agent.cli.app import app


class TestSyncCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_sync_help(self, runner):
        """Test 'omni sync --help' works."""
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "Synchronize system state" in result.output

    @patch("omni.agent.cli.commands.sync._sync_skills")
    @patch("omni.agent.cli.commands.sync._sync_knowledge")
    @patch("omni.agent.cli.commands.sync._sync_memory")
    def test_sync_all(self, mock_memory, mock_knowledge, mock_skills, runner):
        """Test 'omni sync' runs all sync operations."""
        mock_skills.return_value = {"status": "success", "details": "60 skills"}
        mock_knowledge.return_value = {"status": "success", "details": "10 docs"}
        mock_memory.return_value = AsyncMock()
        mock_memory.return_value = {"status": "success", "details": "optimized"}

        # We need to mock the asyncio.run inside sync.py's main or mock the entire sync logic
        # For unit test, we just want to see if it calls the sub-functions
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        assert mock_skills.called
        assert mock_knowledge.called
        assert "System Sync Complete" in result.output


class TestReindexCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_reindex_help(self, runner):
        """Test 'omni reindex --help' works."""
        result = runner.invoke(app, ["reindex", "--help"])
        assert result.exit_code == 0
        assert "Reindex vector databases" in result.output

    @patch("omni.agent.cli.commands.reindex._reindex_skills")
    def test_reindex_skills(self, mock_reindex, runner):
        """Test 'omni reindex skills'."""
        mock_reindex.return_value = {
            "status": "success",
            "database": "skills.lance",
            "tools_indexed": 5,
        }
        result = runner.invoke(app, ["reindex", "skills"])
        assert result.exit_code == 0
        assert mock_reindex.called
        assert "Success" in result.output
        assert "5 tools" in result.output
