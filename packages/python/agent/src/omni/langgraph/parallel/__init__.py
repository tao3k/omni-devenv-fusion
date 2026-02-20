"""
omni.langgraph.parallel - Parallel shard execution for LangGraph workflows.

Provides level-based scheduling (with optional dependency ordering) and
parallel execution within each level. Reusable across researcher, recall,
and other sharded workflows.

Use when:
- You have a list of shards (or chunks) to process.
- Shards can run in parallel (parallel_all=True, default) or respect dependencies.
- Each shard is processed by an async function (e.g. LLM call, repomix + LLM).

Example:
    from omni.langgraph.parallel import build_execution_levels, run_parallel_levels

    levels = build_execution_levels(shards, parallel_all=True)
    results = await run_parallel_levels(levels, process_fn, state)
"""

from omni.langgraph.parallel.levels import (
    build_execution_levels,
    run_parallel_levels,
)

__all__ = [
    "build_execution_levels",
    "run_parallel_levels",
]
