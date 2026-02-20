"""
Level-based parallel execution for sharded workflows.

Builds execution levels from a dependency graph (or single level when parallel_all).
Runs shards within each level in parallel via asyncio.gather.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.langgraph.parallel")

ShardT = dict[str, Any]
StateT = dict[str, Any]
ResultT = TypeVar("ResultT")


def build_execution_levels(
    shards: list[ShardT],
    *,
    parallel_all: bool = True,
    dep_key: str = "dependencies",
    name_key: str = "name",
) -> list[list[tuple[ShardT, int]]]:
    """
    Build execution levels from shards.

    When parallel_all=True (default): single level with all shards (fastest wall clock).
    When parallel_all=False: topological sort by dependencies; each level runs in parallel.

    Args:
        shards: List of shard dicts with at least name_key; optional dep_key list.
        parallel_all: If True, ignore dependencies and put all shards in one level.
        dep_key: Key for dependency list (shard names that must run first).
        name_key: Key for shard name (used to resolve dep references).

    Returns:
        List of levels; each level is list of (shard, 1-based_id).
    """
    if not shards:
        return []

    if parallel_all:
        return [[(s, i + 1) for i, s in enumerate(shards)]]

    return _build_levels_from_deps(shards, dep_key, name_key)


def _normalize_deps(deps: Any) -> list[str]:
    """Normalize dependencies to list of strings. Handles str, list, None."""
    if deps is None:
        return []
    if isinstance(deps, str):
        return [deps.strip()] if deps.strip() else []
    if isinstance(deps, (list, tuple)):
        return [str(d).strip() for d in deps if str(d).strip()]
    return []


def _build_levels_from_deps(
    shards: list[ShardT],
    dep_key: str,
    name_key: str,
) -> list[list[tuple[ShardT, int]]]:
    """Topological sort: level 0 = no deps; each level runs in parallel."""
    name_to_idx: dict[str, int] = {}
    for i, s in enumerate(shards):
        name = s.get(name_key) or f"shard_{i}"
        if name in name_to_idx:
            logger.warning(
                "Duplicate shard name; first index used for dependency resolution",
                name=name,
                first_idx=name_to_idx[name],
                dup_idx=i,
            )
        else:
            name_to_idx[name] = i
    deps: dict[int, set[int]] = {}
    for i, s in enumerate(shards):
        deps[i] = set()
        for dep_name in _normalize_deps(s.get(dep_key)):
            if dep_name in name_to_idx:
                deps[i].add(name_to_idx[dep_name])

    levels: list[list[tuple[ShardT, int]]] = []
    completed: set[int] = set()
    while len(completed) < len(shards):
        level: list[tuple[ShardT, int]] = []
        for i, s in enumerate(shards):
            if i in completed:
                continue
            if deps.get(i, set()) <= completed:
                level.append((s, i + 1))
        if not level:
            for i in range(len(shards)):
                if i not in completed:
                    level.append((shards[i], i + 1))
        for _, shard_id in level:
            completed.add(shard_id - 1)
        levels.append(level)
    return levels


async def run_parallel_levels(
    levels: list[list[tuple[ShardT, int]]],
    process_fn: Callable[[ShardT, int, StateT], Awaitable[ResultT]],
    state: StateT,
    *,
    return_exceptions: bool = False,
    max_concurrent: int | None = None,
) -> list[ResultT | BaseException]:
    """
    Run levels sequentially; within each level, run process_fn in parallel.

    When max_concurrent is set, limits concurrent tasks per level (semaphore).
    Use to avoid API rate limits, memory spikes, or connection exhaustion.

    Args:
        levels: From build_execution_levels.
        process_fn: Async (shard, shard_id, state) -> result.
        state: Shared state passed to each call.
        return_exceptions: If True, return exceptions instead of raising.
        max_concurrent: Max concurrent tasks per level; None = unbounded.

    Returns:
        Flat list of results in level order.
    """
    sem: asyncio.Semaphore | None = (
        asyncio.Semaphore(max_concurrent) if max_concurrent and max_concurrent > 0 else None
    )

    async def _maybe_limited(shard: ShardT, shard_id: int, st: StateT) -> ResultT | BaseException:
        if sem:
            async with sem:
                return await process_fn(shard, shard_id, st)
        return await process_fn(shard, shard_id, st)

    results: list[ResultT | BaseException] = []
    for level in levels:
        tasks = [_maybe_limited(shard, shard_id, state) for shard, shard_id in level]
        level_results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
        for idx, r in enumerate(level_results):
            if isinstance(r, Exception) and not return_exceptions:
                shard, _ = level[idx]
                logger.error(
                    "Shard failed",
                    shard=shard.get("name", "?"),
                    error=str(r),
                )
                raise r
            results.append(r)
    return results
