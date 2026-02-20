"""
Scale benchmarks for skills core: run_skill fast path, service entry.

Skills are the core; these benchmarks guard latency of the user-facing interface
and thinned implementation so we avoid regression and keep scale.

Run: just test-benchmarks
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.test_kit.benchmark import assert_async_latency_under_ms, assert_sync_latency_under_ms

# Thresholds (ms): generous for CI; tighten locally for performance work.
RUN_SKILL_FAST_PATH_MS = 500
KNOWLEDGE_RECALL_MOCK_MS = 300
REINDEX_STATUS_MS = 2000
SYNC_SYMBOLS_MOCK_MS = 3000


@pytest.mark.benchmark
class TestRunSkillScale:
    """Benchmark run_skill (fast path) latency."""

    @pytest.mark.asyncio
    async def test_run_skill_fast_path_latency(self):
        """run_skill fast path (mocked) stays under threshold; guards dispatch overhead."""
        from omni.core.skills import run_skill

        async def one():
            await run_skill("demo", "echo", {"message": "bench"})

        with (
            patch(
                "omni.core.skills.runner._run_fast_path",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch("omni.core.skills.runner._run_via_kernel", new_callable=AsyncMock),
        ):
            await assert_async_latency_under_ms(one, RUN_SKILL_FAST_PATH_MS, iterations=5)

    @pytest.mark.asyncio
    async def test_run_skill_dispatch_with_mock_under_threshold(self):
        """With mocked backend, run_skill dispatch overhead is minimal."""
        from omni.core.skills import run_skill

        async def run_10():
            for _ in range(10):
                await run_skill("knowledge", "recall", {"query": "x", "limit": 1})

        with (
            patch(
                "omni.core.skills.runner._run_fast_path",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch("omni.core.skills.runner._run_via_kernel", new_callable=AsyncMock),
        ):
            start = time.perf_counter()
            await run_10()
            elapsed_ms = (time.perf_counter() - start) * 1000
            avg_per_call = elapsed_ms / 10
            assert avg_per_call < KNOWLEDGE_RECALL_MOCK_MS, (
                f"run_skill dispatch avg {avg_per_call:.1f}ms exceeds {KNOWLEDGE_RECALL_MOCK_MS}ms"
            )


@pytest.mark.benchmark
class TestServiceEntryScale:
    """Benchmark thinned service entry points (reindex_status, sync paths)."""

    def test_reindex_status_latency(self):
        """reindex_status returns within threshold (mocked stores)."""
        from omni.agent.services.reindex import reindex_status

        mock_store = MagicMock()
        mock_store.list_all_tools = MagicMock(return_value=[])

        def run():
            with (
                patch(
                    "omni.agent.services.reindex.get_database_paths",
                    return_value={"skills": "/s", "knowledge": "/k"},
                ),
                patch("omni.foundation.bridge.RustVectorStore", return_value=mock_store),
                patch(
                    "omni.core.knowledge.librarian.Librarian",
                    return_value=MagicMock(is_ready=False),
                ),
            ):
                result = reindex_status()
            assert "skills.lance" in result or "knowledge.lance" in result
            return result

        assert_sync_latency_under_ms(run, REINDEX_STATUS_MS, iterations=1)

    @pytest.mark.asyncio
    async def test_sync_symbols_mocked_latency(self):
        """sync_symbols (mocked indexer) completes under threshold."""
        from omni.agent.services.sync import sync_symbols

        async def run():
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
            assert result.get("status") in ("success", "error")
            return result

        await assert_async_latency_under_ms(run, SYNC_SYMBOLS_MOCK_MS, iterations=1)
