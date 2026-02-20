"""
paper_workflow.py - LangGraph workflow to read any long ingested content in chunks.

Applies to papers, manuals, long docs, or any vector-stored content. Flow:
  1. Preview: recall(query, preview=True, limit=N) → titles/snippets to verify accuracy.
  2. Fetch: recall(query, preview=False, limit=max_chunks) → full chunks.
  3. Slice: split into batches of batch_size; feed each batch to the LLM in turn.

Use when the LLM should consume long content slice by slice (not only papers).
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import Any, TypedDict

from omni.foundation.api.mcp_schema import parse_result_payload
from omni.foundation.config.logging import get_logger
from omni.foundation.runtime.skill_optimization import (
    build_preview_rows,
    normalize_chunk_window,
    split_into_batches,
)
from omni.langgraph.chunked import run_chunked_auto_complete
from omni.rag.retrieval.response import build_recall_chunked_response

logger = get_logger("knowledge.paper_workflow")

# Defaults
DEFAULT_PREVIEW_LIMIT = 10
DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_CHUNKS = 15
DEFAULT_SNIPPET_CHARS = 150


@contextmanager
def _suspend_skills_monitor():
    """Suppress nested skill_command.execute phases for internal recall recursion."""
    try:
        from omni.foundation.runtime.skills_monitor import suppress_skill_command_phase_events
    except Exception:
        yield
        return

    with suppress_skill_command_phase_events():
        yield


class ChunkedRecallState(TypedDict, total=False):
    query: str
    collection: str
    preview_limit: int
    batch_size: int
    max_chunks: int
    preview_results: list
    all_chunks: list
    batches: list
    error: str | None
    queue: list[str]


def _parse_recall_output(out: Any) -> dict[str, Any]:
    """Parse recall output from either direct JSON/dict or MCP envelope."""
    return parse_result_payload(out)


def _get_recall():
    """Import recall from same skill via loader's package (same scripts dir)."""
    try:
        from recall import recall as _recall

        return _recall
    except ImportError:
        pass
    # Use same package as this module (set by skill loader when loading scripts)
    pkg = __package__
    if pkg:
        mod = importlib.import_module(".recall", package=pkg)
        return mod.recall
    raise ImportError("Could not load recall from knowledge.scripts.recall")


async def _node_preview(state: dict[str, Any]) -> dict[str, Any]:
    """Run recall with preview=True to get titles/snippets for accuracy check."""
    recall = _get_recall()

    query = state["query"]
    preview_limit = state.get("preview_limit", DEFAULT_PREVIEW_LIMIT)
    collection = state.get("collection", "knowledge_chunks")
    with _suspend_skills_monitor():
        out = await recall(
            query=query,
            chunked=False,
            limit=preview_limit,
            preview=True,
            snippet_chars=DEFAULT_SNIPPET_CHARS,
            collection=collection,
        )
    data = _parse_recall_output(out)
    state["preview_results"] = data.get("results", [])
    if data.get("status") != "success":
        state["error"] = data.get("error") or data.get("message") or "preview failed"
    return state


async def _node_fetch(state: dict[str, Any]) -> dict[str, Any]:
    """Run recall with full content, then split into batches."""
    recall = _get_recall()

    if state.get("error"):
        return state

    query = state["query"]
    max_chunks = state.get("max_chunks", DEFAULT_MAX_CHUNKS)
    batch_size = state.get("batch_size", DEFAULT_BATCH_SIZE)
    collection = state.get("collection", "knowledge_chunks")
    with _suspend_skills_monitor():
        out = await recall(
            query=query,
            chunked=False,
            limit=max_chunks,
            preview=False,
            collection=collection,
        )
    data = _parse_recall_output(out)
    if data.get("status") != "success":
        state["error"] = data.get("error") or data.get("message") or "fetch failed"
        state["all_chunks"] = []
        state["batches"] = []
        return state
    chunks = data.get("results", [])
    state["all_chunks"] = chunks
    if not state.get("preview_results"):
        state["preview_results"] = build_preview_rows(
            chunks,
            preview_limit=state.get("preview_limit", DEFAULT_PREVIEW_LIMIT),
            snippet_chars=DEFAULT_SNIPPET_CHARS,
        )
    # Split into batches for chunked read.
    state["batches"] = split_into_batches(chunks, batch_size=batch_size)
    return state


async def run_chunked_recall(
    query: str,
    preview_limit: int = 10,
    batch_size: int = 5,
    max_chunks: int = 15,
    collection: str = "knowledge_chunks",
    profile: str = "balanced",
) -> dict:
    """
    Run chunked-recall workflow: preview → fetch full → split into batches.
    Used as the default path for knowledge.recall (no separate skill command).
    Returns a dict (not JSON string) for recall.py to serialize.
    """
    normalized = normalize_chunk_window(
        limit=max_chunks,
        preview_limit=preview_limit,
        batch_size=batch_size,
        max_chunks=max_chunks,
        chunked=True,
        profile=profile,
        enforce_limit_cap=True,
    )
    preview_limit = normalized.preview_limit
    batch_size = normalized.batch_size
    max_chunks = max(batch_size, normalized.max_chunks)

    initial: ChunkedRecallState = {
        "query": query,
        "preview_limit": preview_limit,
        "batch_size": batch_size,
        "max_chunks": max_chunks,
        "collection": collection,
        "preview_results": [],
        "all_chunks": [],
        "batches": [],
        "error": None,
        # One-pass fast path: fetch once, then derive preview from fetched chunks.
        "queue": ["fetch"],
    }

    def _run_start() -> ChunkedRecallState:
        return dict(initial)

    async def _run_step(state: dict[str, Any]) -> dict[str, Any]:
        queue = list(state.get("queue", []))
        if not queue:
            return state
        step = queue.pop(0)
        state["queue"] = queue
        state["current_chunk"] = {"name": step}
        if step == "preview":
            return await _node_preview(state)
        if step == "fetch":
            return await _node_fetch(state)
        state["error"] = f"Unknown chunked step: {step}"
        return state

    async def _run_synthesize(state: dict[str, Any]) -> dict[str, Any]:
        all_chunks = state.get("all_chunks", [])
        state["final_report"] = build_recall_chunked_response(
            query=query,
            status="error" if state.get("error") else "success",
            error=state.get("error"),
            preview_results=state.get("preview_results", []),
            batches=state.get("batches", []),
            results=all_chunks,
        )
        return state

    try:
        result = await run_chunked_auto_complete(
            "recall_chunked_one_shot",
            _run_start,
            _run_step,
            _run_synthesize,
            queue_key="queue",
        )
    except Exception as e:
        logger.error("Chunked recall workflow failed", error=str(e))
        return build_recall_chunked_response(
            query=query,
            status="error",
            error=str(e),
            preview_results=[],
            batches=[],
            results=[],
        )

    if not result.get("success"):
        return build_recall_chunked_response(
            query=query,
            status="error",
            error=result.get("error", "chunked workflow failed"),
            preview_results=[],
            batches=[],
            results=[],
        )

    payload = result.get("result")
    if isinstance(payload, dict) and "query" in payload and "results" in payload:
        return build_recall_chunked_response(
            query=str(payload.get("query", query)),
            status=str(payload.get("status", "success")),
            error=payload.get("error"),
            preview_results=payload.get("preview_results", []),
            batches=payload.get("batches", []),
            results=payload.get("results", []),
        )

    return build_recall_chunked_response(
        query=query,
        status="error",
        error="Invalid chunked workflow payload",
        preview_results=[],
        batches=[],
        results=[],
    )
