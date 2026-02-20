"""
LangGraph node helpers for chunked workflows.

Factory to build a "process next chunk" node that reads queue from state,
processes one chunk via a callable, and returns updated state (queue popped,
accumulated appended). Use with StateGraph for consistent long-content handling.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.langgraph.chunked.state import ChunkedWorkflowState

logger = get_logger("omni.langgraph.chunked")


def make_process_chunk_node(
    process_one: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]
    ],
    *,
    queue_key: str = "queue",
    accumulated_key: str = "accumulated",
    current_key: str = "current_chunk",
) -> Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]:
    """
    Build a LangGraph node that processes the next chunk from state.

    The node: pops the first item from state[queue_key], sets state[current_key],
    calls process_one(state), then merges back: queue = queue[1:], accumulated += [result].
    process_one receives the full state (with current_chunk set) and returns state updates
    (e.g. a "summary" or "result" key); that result is appended to accumulated.

    Args:
        process_one: Callable(state) -> state updates (or awaitable). Should read
            state[current_key] and return dict with at least one key to append to accumulated.
        queue_key: State key for the chunk queue (default "queue").
        accumulated_key: State key for accumulated results (default "accumulated").
        current_key: State key for the chunk being processed (default "current_chunk").

    Returns:
        A node function (state) -> updated state, for use with workflow.add_node(...).
    """

    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        queue = list(state.get(queue_key, []))
        if not queue:
            return {**state, "error": "No chunks in queue"}
        chunk = queue[0]
        rest = queue[1:]
        state_with_current = {**state, current_key: chunk, queue_key: rest}
        out = process_one(state_with_current)
        import asyncio

        if asyncio.iscoroutine(out):
            updates = await out
        else:
            updates = out
        # Append this chunk's result to accumulated (convention: process_one returns e.g. {"summary": "..."})
        acc = list(state.get(accumulated_key, []))
        result_item = updates.get("summary", updates.get("result", updates))
        acc.append(result_item)
        return {
            **state,
            **updates,
            queue_key: rest,
            accumulated_key: acc,
            current_key: chunk,
        }

    return _node


def make_synthesize_node(
    synthesize: Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]],
    *,
    accumulated_key: str = "accumulated",
    result_key: str = "final_report",
) -> Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]:
    """
    Build a LangGraph node that runs synthesis over accumulated results.

    Args:
        synthesize: Callable(state) -> state updates (e.g. {result_key: "..."}). Async or sync.
        accumulated_key: State key for accumulated chunk results.
        result_key: State key for the final report/result.

    Returns:
        A node function (state) -> updated state.
    """

    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        out = synthesize(state)
        if asyncio.iscoroutine(out):
            return await out
        return {**state, **out}

    return _node
