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

        # For unit test, we only verify sub-sync handlers are invoked.
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        assert mock_skills.called
        assert mock_knowledge.called
        assert "System Sync Complete" in result.output

    @patch("omni.agent.cli.commands.sync.run_async_blocking")
    def test_sync_knowledge_uses_shared_async_runner(self, mock_run_async_blocking, runner):
        """sync knowledge should execute via shared run_async_blocking helper."""
        mock_run_async_blocking.side_effect = lambda coro: (coro.close(), {"status": "success"})[1]

        result = runner.invoke(app, ["sync", "knowledge"])

        assert result.exit_code == 0
        assert mock_run_async_blocking.called


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

    @pytest.mark.asyncio
    async def test_run_async_blocking_works_inside_running_loop(self):
        """Shared runner should execute coroutine when an event loop is already running."""
        from omni.foundation.utils.asyncio import run_async_blocking

        async def _sample():
            return 42

        assert run_async_blocking(_sample()) == 42

    @patch("omni.agent.cli.commands.reindex._reindex_skills_and_router")
    @patch("omni.agent.cli.commands.reindex.get_database_path")
    @patch("omni.foundation.bridge.get_vector_store")
    @patch("omni.agent.cli.commands.reindex.run_async_blocking")
    def test_sync_router_refreshes_skills_first(
        self,
        mock_run_async_blocking,
        mock_get_vector_store,
        mock_get_db_path,
        mock_reindex_atomic,
    ):
        """Router sync must refresh skills first to keep router/skills in lockstep."""
        from omni.agent.cli.commands.reindex import _sync_router_from_skills

        mock_reindex_atomic.return_value = {
            "status": "success",
            "skills_tools_indexed": 12,
            "router_tools_indexed": 12,
        }
        mock_get_db_path.return_value = "/tmp/router.lance"
        mock_store = MagicMock()
        mock_get_vector_store.return_value = mock_store
        mock_run_async_blocking.return_value = 12

        result = _sync_router_from_skills()

        assert result["status"] == "success"
        assert result["tools_indexed"] == 12
        mock_reindex_atomic.assert_called_once_with(clear=False)
        mock_get_vector_store.assert_not_called()
        mock_store.index_skill_tools.assert_not_called()

    @patch("omni.agent.cli.commands.reindex._reindex_skills_and_router")
    @patch("omni.agent.cli.commands.reindex.get_database_path")
    @patch("omni.foundation.bridge.get_vector_store")
    @patch("omni.agent.cli.commands.reindex.run_async_blocking")
    def test_sync_router_can_skip_skills_refresh(
        self,
        mock_run_async_blocking,
        mock_get_vector_store,
        mock_get_db_path,
        mock_reindex_atomic,
    ):
        """Router sync can skip skills refresh when caller already refreshed snapshot."""
        from omni.agent.cli.commands.reindex import _sync_router_from_skills

        mock_get_db_path.return_value = "/tmp/router.lance"
        mock_store = MagicMock()
        mock_get_vector_store.return_value = mock_store
        mock_run_async_blocking.return_value = 12

        result = _sync_router_from_skills(refresh_skills=False)

        assert result["status"] == "success"
        assert result["tools_indexed"] == 12
        mock_reindex_atomic.assert_not_called()

    @patch("omni.agent.cli.commands.reindex._sync_router_from_skills")
    def test_reindex_router_default_is_atomic(self, mock_sync_router, runner):
        """`omni reindex router` should default to atomic skills+router sync."""
        mock_sync_router.return_value = {
            "status": "success",
            "database": "router.lance",
            "tools_indexed": 7,
        }

        result = runner.invoke(app, ["reindex", "router"])

        assert result.exit_code == 0
        mock_sync_router.assert_called_once_with(refresh_skills=True)

    @patch("omni.agent.cli.commands.reindex._sync_router_from_skills")
    def test_reindex_router_only_router_flag(self, mock_sync_router, runner):
        """`--only-router` should skip atomic skills refresh."""
        mock_sync_router.return_value = {
            "status": "success",
            "database": "router.lance",
            "tools_indexed": 7,
        }

        result = runner.invoke(app, ["reindex", "router", "--only-router"])

        assert result.exit_code == 0
        mock_sync_router.assert_called_once_with(refresh_skills=False)

    @patch("omni.agent.cli.commands.reindex.get_setting")
    @patch("omni.agent.cli.commands.reindex._read_embedding_signature")
    @patch("omni.agent.cli.commands.reindex._write_embedding_signature")
    def test_embedding_signature_initialized_without_reindex(
        self,
        mock_write_sig,
        mock_read_sig,
        mock_get_setting,
    ):
        from omni.agent.cli.commands.reindex import ensure_embedding_index_compatibility

        mock_read_sig.return_value = None
        mock_get_setting.side_effect = lambda key, default=None: {
            "embedding.auto_reindex_on_change": True,
            "embedding.model": "Qwen/Qwen3-Embedding-0.6B",
            "embedding.dimension": 1024,
            "embedding.provider": "",
        }.get(key, default)

        result = ensure_embedding_index_compatibility(auto_fix=True)

        assert result["status"] == "initialized"
        mock_write_sig.assert_called_once()

    @patch("omni.agent.cli.commands.reindex._reindex_skills_and_router")
    @patch("omni.agent.cli.commands.reindex.get_setting")
    @patch("omni.agent.cli.commands.reindex._read_embedding_signature")
    @patch("omni.agent.cli.commands.reindex._write_embedding_signature")
    def test_embedding_signature_mismatch_triggers_reindex(
        self,
        mock_write_sig,
        mock_read_sig,
        mock_get_setting,
        mock_reindex_atomic,
    ):
        from omni.agent.cli.commands.reindex import ensure_embedding_index_compatibility

        mock_read_sig.return_value = {
            "embedding_model": "old",
            "embedding_dimension": 768,
            "embedding_provider": "",
        }
        mock_get_setting.side_effect = lambda key, default=None: {
            "embedding.auto_reindex_on_change": True,
            "embedding.model": "Qwen/Qwen3-Embedding-0.6B",
            "embedding.dimension": 1024,
            "embedding.provider": "",
        }.get(key, default)
        mock_reindex_atomic.return_value = {
            "status": "success",
            "skills_tools_indexed": 69,
            "router_tools_indexed": 69,
        }

        result = ensure_embedding_index_compatibility(auto_fix=True)

        assert result["status"] == "reindexed"
        mock_reindex_atomic.assert_called_once_with(clear=True)
        mock_write_sig.assert_called_once()
