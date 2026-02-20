"""Tests for omni.langgraph.parallel (build_execution_levels, run_parallel_levels)."""

import asyncio

import pytest

from omni.langgraph.parallel import build_execution_levels, run_parallel_levels


class TestBuildExecutionLevels:
    """Tests for build_execution_levels."""

    def test_parallel_all_single_level(self):
        """parallel_all=True puts all shards in one level."""
        shards = [
            {"name": "A", "targets": [], "description": "A", "dependencies": ["B"]},
            {"name": "B", "targets": [], "description": "B", "dependencies": []},
        ]
        levels = build_execution_levels(shards, parallel_all=True)
        assert len(levels) == 1
        assert len(levels[0]) == 2

    def test_parallel_all_empty(self):
        """Empty shards returns empty levels."""
        assert build_execution_levels([], parallel_all=True) == []

    def test_deps_respects_order(self):
        """parallel_all=False: topological order; same level runs in parallel."""
        shards = [
            {"name": "Core", "targets": [], "description": "Core", "dependencies": []},
            {"name": "API", "targets": [], "description": "API", "dependencies": ["Core"]},
            {"name": "CLI", "targets": [], "description": "CLI", "dependencies": ["Core"]},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        assert len(levels) == 2
        assert len(levels[0]) == 1
        assert levels[0][0][0]["name"] == "Core"
        assert len(levels[1]) == 2
        names_l1 = {s["name"] for s, _ in levels[1]}
        assert names_l1 == {"API", "CLI"}

    def test_deps_chain(self):
        """Linear chain: A -> B -> C gives 3 levels."""
        shards = [
            {"name": "A", "targets": [], "description": "A", "dependencies": []},
            {"name": "B", "targets": [], "description": "B", "dependencies": ["A"]},
            {"name": "C", "targets": [], "description": "C", "dependencies": ["B"]},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        assert len(levels) == 3
        assert [levels[i][0][0]["name"] for i in range(3)] == ["A", "B", "C"]

    def test_deps_as_string_normalized(self):
        """dependencies as string 'Core' is normalized to ['Core']."""
        shards = [
            {"name": "Core", "targets": [], "description": "Core", "dependencies": []},
            {"name": "API", "targets": [], "description": "API", "dependencies": "Core"},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        assert len(levels) == 2
        assert levels[0][0][0]["name"] == "Core"
        assert levels[1][0][0]["name"] == "API"

    def test_duplicate_names_first_wins(self):
        """Duplicate shard names: first index used for dependency resolution."""
        shards = [
            {"name": "Core", "targets": [], "description": "Core", "dependencies": []},
            {"name": "Core", "targets": [], "description": "Core2", "dependencies": ["Core"]},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        assert len(levels) == 2
        assert levels[0][0][0]["name"] == "Core"
        assert levels[1][0][0]["name"] == "Core"


@pytest.mark.asyncio
class TestRunParallelLevels:
    """Tests for run_parallel_levels."""

    async def test_runs_levels_sequentially(self):
        """Levels run in order; within level, tasks run in parallel."""
        call_order: list[str] = []

        async def process(shard: dict, shard_id: int, state: dict):
            call_order.append(f"{shard['name']}_{shard_id}")
            return shard["name"]

        shards = [
            {"name": "A", "targets": [], "description": "A", "dependencies": []},
            {"name": "B", "targets": [], "description": "B", "dependencies": ["A"]},
        ]
        levels = build_execution_levels(shards, parallel_all=False)
        results = await run_parallel_levels(levels, process, {})
        assert results == ["A", "B"]
        assert "A_1" in call_order
        assert "B_2" in call_order

    async def test_parallel_all_runs_all_together(self):
        """parallel_all: all shards processed in one level."""

        async def process(shard: dict, shard_id: int, state: dict):
            return shard["name"] + str(shard_id)

        shards = [
            {"name": "X", "targets": [], "description": "X"},
            {"name": "Y", "targets": [], "description": "Y"},
        ]
        levels = build_execution_levels(shards, parallel_all=True)
        results = await run_parallel_levels(levels, process, {})
        assert set(results) == {"X1", "Y2"}

    async def test_max_concurrent_limits_parallelism(self):
        """
        max_concurrent enforces semaphore: never more than N tasks run at once.

        Uses 12 shards with max_concurrent=3; each task sleeps and records
        concurrent count. Peak must never exceed 3.
        """
        concurrent_count = 0
        peak_concurrent = 0
        lock = asyncio.Lock()

        async def process(shard: dict, shard_id: int, state: dict):
            nonlocal concurrent_count, peak_concurrent
            async with lock:
                concurrent_count += 1
                peak_concurrent = max(peak_concurrent, concurrent_count)
            await asyncio.sleep(0.02)
            async with lock:
                concurrent_count -= 1
            return shard["name"]

        shards = [{"name": f"S{i}", "targets": [], "description": f"S{i}"} for i in range(12)]
        levels = build_execution_levels(shards, parallel_all=True)
        results = await run_parallel_levels(
            levels,
            process,
            {},
            max_concurrent=3,
        )
        assert len(results) == 12
        assert peak_concurrent <= 3, f"Peak concurrent {peak_concurrent} exceeded limit 3"

    async def test_max_concurrent_none_is_unbounded(self):
        """max_concurrent=None runs all tasks in parallel (no semaphore)."""
        concurrent_count = 0
        peak_concurrent = 0
        lock = asyncio.Lock()

        async def process(shard: dict, shard_id: int, state: dict):
            nonlocal concurrent_count, peak_concurrent
            async with lock:
                concurrent_count += 1
                peak_concurrent = max(peak_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            async with lock:
                concurrent_count -= 1
            return shard["name"]

        shards = [{"name": f"T{i}", "targets": [], "description": f"T{i}"} for i in range(5)]
        levels = build_execution_levels(shards, parallel_all=True)
        results = await run_parallel_levels(levels, process, {}, max_concurrent=None)
        assert len(results) == 5
        assert peak_concurrent == 5, f"Expected 5 concurrent, got {peak_concurrent}"

    async def test_max_concurrent_zero_or_negative_ignored(self):
        """max_concurrent=0 or negative is treated as unbounded (no semaphore)."""

        async def process(shard: dict, shard_id: int, state: dict):
            return shard["name"]

        shards = [{"name": "A", "targets": [], "description": "A"}]
        levels = build_execution_levels(shards, parallel_all=True)
        r0 = await run_parallel_levels(levels, process, {}, max_concurrent=0)
        r1 = await run_parallel_levels(levels, process, {}, max_concurrent=-1)
        assert r0 == ["A"] and r1 == ["A"]
