"""
Data interface contract tests for thinned CLI services.

Ensures return shapes of run_skill, reindex, sync, and run_entry stay stable
so CLI and MCP callers can rely on the data contract. Scale is our core;
these tests guard the interface.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@contextmanager
def _noop_lock():
    yield


class TestRunSkillContract:
    """Contract: omni.core.skills.run_skill return shape."""

    @pytest.mark.asyncio
    async def test_run_skill_returns_string_or_dict(self):
        """run_skill may return str (JSON) or dict; CLI handles both."""
        from omni.core.skills import run_skill

        with (
            patch("omni.core.skills.runner._run_fast_path", new_callable=AsyncMock) as mock_fast,
            patch("omni.core.skills.runner._run_via_kernel", new_callable=AsyncMock),
        ):
            mock_fast.return_value = '{"status":"success","results":[]}'
            out = await run_skill("knowledge", "recall", {"query": "x", "limit": 1})
        assert out is not None
        assert isinstance(out, str)
        data = json.loads(out)
        assert "status" in data
        assert "results" in data

    @pytest.mark.asyncio
    async def test_run_skill_dict_return_contract(self):
        """When skill returns dict, keys are preserved."""
        from omni.core.skills import run_skill

        with (
            patch("omni.core.skills.runner._run_fast_path", new_callable=AsyncMock) as mock_fast,
            patch("omni.core.skills.runner._run_via_kernel", new_callable=AsyncMock),
        ):
            mock_fast.return_value = {"status": "ok", "count": 0}
            out = await run_skill("demo", "echo", {"message": "hi"})
        assert isinstance(out, dict)
        assert "status" in out


class TestReindexServiceContract:
    """Contract: omni.agent.services.reindex return shapes."""

    def test_reindex_skills_only_returns_status_and_tools(self):
        """reindex_skills_only returns dict with status, database, tools_indexed."""
        from omni.agent.services.reindex import reindex_skills_only

        mock_store = MagicMock()
        mock_store.drop_table = AsyncMock(return_value=None)
        mock_store.index_skill_tools_dual = AsyncMock(return_value=(0, 0))
        mock_store.list_all = AsyncMock(return_value=[])

        with (
            patch("omni.agent.services.reindex._reindex_lock", _noop_lock),
            patch(
                "omni.agent.services.reindex.get_database_path", return_value="/tmp/skills.lance"
            ),
            patch("omni.foundation.config.skills.SKILLS_DIR", return_value="/tmp/skills"),
            patch("omni.foundation.bridge.RustVectorStore", return_value=mock_store),
            patch(
                "omni.agent.services.reindex._validate_skills_schema", return_value={"skills": {}}
            ),
            patch("omni.agent.services.reindex._build_relationship_graph_after_skills_reindex"),
        ):
            result = reindex_skills_only(clear=False)
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ("success", "error")
        if result["status"] == "success":
            assert "database" in result
            assert "tools_indexed" in result or "skills_tools_indexed" in result

    def test_reindex_status_returns_db_keys(self):
        """reindex_status returns dict keyed by db name (e.g. skills.lance)."""
        from omni.agent.services.reindex import reindex_status

        mock_store = MagicMock()
        mock_store.list_all_tools = MagicMock(return_value=[])

        with (
            patch(
                "omni.agent.services.reindex.get_database_paths",
                return_value={"skills": "/s", "knowledge": "/k"},
            ),
            patch("omni.foundation.bridge.RustVectorStore", return_value=mock_store),
            patch(
                "omni.core.knowledge.librarian.Librarian", return_value=MagicMock(is_ready=False)
            ),
        ):
            result = reindex_status()
        assert isinstance(result, dict)
        assert "skills.lance" in result or "knowledge.lance" in result or len(result) >= 1
        for v in result.values():
            assert isinstance(v, dict)
            assert "status" in v

    def test_reindex_clear_returns_cleared_list(self):
        """reindex_clear returns status and cleared list."""
        from omni.agent.services.reindex import reindex_clear

        mock_store = MagicMock()
        mock_store.drop_table = AsyncMock(return_value=None)

        with (
            patch("omni.foundation.bridge.RustVectorStore", return_value=mock_store),
            patch(
                "omni.core.knowledge.librarian.Librarian", return_value=MagicMock(is_ready=False)
            ),
        ):
            result = reindex_clear()
        assert result["status"] == "success"
        assert "cleared" in result
        assert isinstance(result["cleared"], list)


class TestSyncServiceContract:
    """Contract: omni.agent.services.sync return shapes."""

    @pytest.mark.asyncio
    async def test_sync_symbols_returns_status_details_elapsed(self):
        """sync_symbols returns dict with status, details, elapsed."""
        from omni.agent.services.sync import sync_symbols

        with (
            patch("omni.agent.services.sync.sync_log"),
            patch("omni.foundation.runtime.gitops.get_project_root", return_value="/tmp"),
            patch(
                "omni.core.knowledge.symbol_indexer.SymbolIndexer",
                return_value=MagicMock(
                    build=MagicMock(return_value={"unique_symbols": 0, "indexed_files": 0})
                ),
            ),
        ):
            result = await sync_symbols(clear=False, verbose=False)
        assert isinstance(result, dict)
        assert "status" in result
        assert "details" in result
        assert result["status"] in ("success", "error")

    @pytest.mark.asyncio
    async def test_sync_all_returns_tuple_stats_elapsed(self):
        """sync_all returns (stats dict, total_elapsed float)."""
        from omni.agent.services.sync import sync_all

        with (
            patch("omni.agent.services.sync.sync_log"),
            patch(
                "omni.foundation.services.index_dimension.check_all_vector_stores_dimension",
                return_value=MagicMock(is_consistent=True, issues=[], stores={}),
            ),
            patch("omni.foundation.services.index_dimension.ensure_embedding_signature_written"),
            patch(
                "omni.agent.services.sync.sync_symbols",
                new_callable=AsyncMock,
                return_value={"status": "success", "details": ""},
            ),
            patch(
                "omni.agent.services.sync.sync_skills",
                new_callable=AsyncMock,
                return_value={"status": "success", "details": ""},
            ),
            patch(
                "omni.agent.services.sync.sync_router_init",
                new_callable=AsyncMock,
                return_value={"status": "success"},
            ),
            patch(
                "omni.agent.services.sync.sync_knowledge",
                new_callable=AsyncMock,
                return_value={"status": "success", "details": ""},
            ),
            patch(
                "omni.agent.services.sync.sync_memory",
                new_callable=AsyncMock,
                return_value={"status": "success", "details": ""},
            ),
        ):
            stats, elapsed = await sync_all(verbose=False)
        assert isinstance(stats, dict)
        assert "symbols" in stats
        assert "skills" in stats
        assert "knowledge" in stats
        assert "memory" in stats
        assert isinstance(elapsed, (int, float))
        assert elapsed >= 0


class TestRunEntryContract:
    """Contract: omni.agent.workflows.run_entry return shapes."""

    @pytest.mark.asyncio
    async def test_execute_task_via_kernel_returns_session_output_steps(self):
        """execute_task_via_kernel returns dict with session_id, output, step_count, status."""
        from omni.agent.workflows.run_entry import execute_task_via_kernel

        with (
            patch(
                "omni.core.kernel.engine.get_kernel",
                return_value=MagicMock(
                    initialize=AsyncMock(),
                    start=AsyncMock(),
                    shutdown=AsyncMock(),
                    skill_context=MagicMock(_skills={}),
                ),
            ),
            patch(
                "omni.core.router.main.RouterRegistry.get",
                return_value=MagicMock(
                    initialize=AsyncMock(),
                    route=AsyncMock(return_value=None),
                ),
            ),
            patch(
                "omni.agent.core.omni.OmniLoop",
                return_value=MagicMock(
                    run=AsyncMock(return_value="done"),
                    session_id="s1",
                    step_count=1,
                    tool_calls_count=1,
                ),
            ),
        ):
            result = await execute_task_via_kernel("hello", max_steps=5, verbose=False)
        assert isinstance(result, dict)
        assert "session_id" in result
        assert "output" in result
        assert "step_count" in result
        assert "status" in result
        assert result["status"] == "completed"
