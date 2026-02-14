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

    @patch("omni.agent.cli.commands.reindex._reindex_skills_only")
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

    def test_reindex_router_command_removed(self, runner):
        """`omni reindex router` no longer exists; use `omni reindex skills`."""
        result = runner.invoke(app, ["reindex", "router"])
        assert result.exit_code != 0

    def test_sync_router_command_removed(self, runner):
        """`omni sync router` no longer exists; use `omni sync skills`."""
        result = runner.invoke(app, ["sync", "router"])
        assert result.exit_code != 0

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

    @patch("omni.agent.cli.commands.reindex._reindex_skills_only")
    @patch("omni.agent.cli.commands.reindex.get_setting")
    @patch("omni.agent.cli.commands.reindex._read_embedding_signature")
    @patch("omni.agent.cli.commands.reindex._write_embedding_signature")
    def test_embedding_signature_mismatch_triggers_reindex(
        self,
        mock_write_sig,
        mock_read_sig,
        mock_get_setting,
        mock_reindex_skills,
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
        mock_reindex_skills.return_value = {
            "status": "success",
            "skills_tools_indexed": 69,
        }

        result = ensure_embedding_index_compatibility(auto_fix=True)

        assert result["status"] == "reindexed"
        mock_reindex_skills.assert_called_once_with(clear=True)
        mock_write_sig.assert_called_once()


class TestSyncReindexUnifiedPath:
    """Ensure sync and reindex use the same skills path and API (unified contract).

    Prevents regression where sync writes to a different store/path than reindex
    or route test reads from, which would make 'omni sync' appear to have no effect.
    """

    @pytest.mark.asyncio
    async def test_sync_skills_uses_get_database_path_skills(self):
        """_sync_skills must use get_database_path('skills') so it writes to the same DB as reindex."""
        from omni.agent.cli.commands.sync import _sync_skills

        with (
            patch(
                "omni.foundation.config.database.get_database_path",
                return_value="/cache/omni-vector/skills.lance",
            ) as mock_get_path,
            patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store,
            patch("omni.foundation.config.skills.SKILLS_DIR", return_value=__file__),
        ):
            mock_store = MagicMock()
            mock_store.index_skill_tools_dual = AsyncMock(return_value=(3, 3))
            mock_get_store.return_value = mock_store

            with (
                patch(
                    "omni.agent.cli.commands.reindex._build_relationship_graph_after_skills_reindex",
                ) as mock_build_graph,
                patch(
                    "omni.foundation.services.index_dimension.ensure_embedding_signature_written",
                ),
                patch(
                    "omni.core.skills.discovery.SkillDiscoveryService",
                ) as mock_discovery_cls,
            ):
                mock_discovery_cls.return_value.discover_all = AsyncMock(return_value=[MagicMock()])

                await _sync_skills()

        mock_get_path.assert_called_once_with("skills")
        mock_get_store.assert_called_once_with("/cache/omni-vector/skills.lance")
        mock_build_graph.assert_called_once_with("/cache/omni-vector/skills.lance")

    @pytest.mark.asyncio
    async def test_sync_skills_uses_index_skill_tools_dual(self):
        """_sync_skills must use index_skill_tools_dual(skills_path, 'skills', 'skills') like reindex."""
        from omni.agent.cli.commands.sync import _sync_skills

        with (
            patch(
                "omni.foundation.config.database.get_database_path",
                return_value="/cache/omni-vector/skills.lance",
            ),
            patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store,
            patch("omni.foundation.config.skills.SKILLS_DIR", return_value=__file__),
        ):
            mock_store = MagicMock()
            mock_dual = AsyncMock(return_value=(2, 2))
            mock_store.index_skill_tools_dual = mock_dual
            mock_get_store.return_value = mock_store

            with (
                patch(
                    "omni.agent.cli.commands.reindex._build_relationship_graph_after_skills_reindex",
                ),
                patch(
                    "omni.foundation.services.index_dimension.ensure_embedding_signature_written",
                ),
                patch(
                    "omni.core.skills.discovery.SkillDiscoveryService",
                ) as mock_discovery_cls,
            ):
                mock_discovery_cls.return_value.discover_all = AsyncMock(return_value=[])

                await _sync_skills()

        mock_dual.assert_called_once()
        call_args = mock_dual.call_args
        assert call_args[0][1] == "skills"
        assert call_args[0][2] == "skills"

    @pytest.mark.asyncio
    async def test_sync_skills_builds_relationship_graph(self):
        """_sync_skills must build the relationship graph after indexing (same as reindex)."""
        from omni.agent.cli.commands.sync import _sync_skills

        with (
            patch(
                "omni.foundation.config.database.get_database_path",
                return_value="/cache/omni-vector/skills.lance",
            ),
            patch("omni.foundation.bridge.rust_vector.get_vector_store") as mock_get_store,
            patch("omni.foundation.config.skills.SKILLS_DIR", return_value=__file__),
        ):
            mock_store = MagicMock()
            mock_store.index_skill_tools_dual = AsyncMock(return_value=(1, 1))
            mock_get_store.return_value = mock_store

            with (
                patch(
                    "omni.agent.cli.commands.reindex._build_relationship_graph_after_skills_reindex",
                ) as mock_build_graph,
                patch(
                    "omni.foundation.services.index_dimension.ensure_embedding_signature_written",
                ),
                patch(
                    "omni.core.skills.discovery.SkillDiscoveryService",
                ) as mock_discovery_cls,
            ):
                mock_discovery_cls.return_value.discover_all = AsyncMock(return_value=[])

                await _sync_skills()

        mock_build_graph.assert_called_once_with("/cache/omni-vector/skills.lance")

    def test_reindex_skills_only_uses_get_database_path_skills(self):
        """_reindex_skills_only must use get_database_path('skills') for the store path."""
        from omni.agent.cli.commands.reindex import _reindex_skills_only

        with (
            patch(
                "omni.agent.cli.commands.reindex.get_database_path",
                return_value="/cache/omni-vector/skills.lance",
            ) as mock_get_path,
            patch(
                "omni.foundation.bridge.RustVectorStore",
            ) as mock_store_cls,
            patch(
                "omni.agent.cli.commands.reindex._reindex_lock",
            ) as mock_lock,
            patch(
                "omni.agent.cli.commands.reindex._build_relationship_graph_after_skills_reindex",
            ),
        ):
            mock_lock.return_value.__enter__ = lambda self: None
            mock_lock.return_value.__exit__ = lambda self, *a: None

            mock_store = MagicMock()
            mock_store.drop_table = AsyncMock(return_value=None)
            mock_dual = AsyncMock(return_value=(4, 4))
            mock_store.index_skill_tools_dual = mock_dual
            mock_store.list_all = AsyncMock(return_value=[])  # for _validate_skills_schema
            mock_store_cls.return_value = mock_store

            result = _reindex_skills_only(clear=False)

        assert result.get("status") == "success"
        mock_get_path.assert_called_with("skills")
        mock_dual.assert_called_once()
        call_args = mock_dual.call_args[0]
        assert call_args[1] == "skills"
        assert call_args[2] == "skills"
