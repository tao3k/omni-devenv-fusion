"""
Step runner for chunked workflows: start → process chunk → … → synthesize.

Shared orchestration helpers over ChunkedWorkflowEngine.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from omni.foundation.context_delivery import (
    ChunkedSession,
    ChunkedSessionStore,
    normalize_chunked_action_name,
)
from omni.langgraph.chunked.engine import ChunkedWorkflowEngine, WorkflowStoreLike
from omni.langgraph.chunked.plan import collect_chunk_progress
from omni.langgraph.chunked.result import build_summary_payload_from_chunked_step_result
from omni.langgraph.parallel import run_parallel_levels


def normalize_full_document_source(source: str) -> str:
    """Normalize full-document source into a basename-like suffix for matching."""
    source_suffix = (source or "").strip()
    if source_suffix and not source_suffix.startswith("/"):
        source_suffix = source_suffix.split("/")[-1]
    return source_suffix


def collect_full_document_rows(
    entries: list[dict[str, Any]],
    *,
    source: str,
    metadata_key: str = "metadata",
    content_key: str = "content",
    source_key: str = "source",
    chunk_index_key: str = "chunk_index",
    score: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Filter + deduplicate vector entries for full-document reads.

    Rules:
    - Match source by suffix (same behavior as knowledge.recall).
    - Deduplicate by chunk_index (keep first occurrence).
    - Return rows sorted by (chunk_index, source).
    """
    source_suffix = normalize_full_document_source(source)
    matched: list[dict[str, Any]] = []
    seen_indices: set[int] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get(metadata_key) or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata) if metadata else {}
            except json.JSONDecodeError:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        entry_source = str(metadata.get(source_key) or "")
        if source_suffix and not (
            entry_source.endswith(source_suffix) or source_suffix in entry_source
        ):
            continue

        raw_index = metadata.get(chunk_index_key, -1)
        try:
            chunk_index = int(raw_index)
        except (TypeError, ValueError):
            chunk_index = -1
        if chunk_index in seen_indices:
            continue
        seen_indices.add(chunk_index)

        matched.append(
            {
                "content": entry.get(content_key, ""),
                "source": entry_source,
                "chunk_index": chunk_index,
                "score": score,
            }
        )

    matched.sort(key=lambda row: (row.get("chunk_index", -1), row.get("source", "")))
    return matched


def build_full_document_payload(
    *,
    rows: list[dict[str, Any]],
    source: str,
    batch_size: Any,
    batch_index: Any,
    action: str = "full_document",
    batch_index_param: str = "full_document_batch_index",
) -> dict[str, Any]:
    """Build normalized full-document payload with optional batching."""
    source_suffix = normalize_full_document_source(source)
    total_count = len(rows)

    try:
        size = int(batch_size)
    except (TypeError, ValueError):
        size = 0
    size = max(0, size)

    try:
        idx = int(batch_index)
    except (TypeError, ValueError):
        idx = 0
    idx = max(0, idx)

    if size > 0:
        batch_count = (total_count + size - 1) // size if total_count > 0 else 0
        start = idx * size
        end = min(start + size, total_count)
        batch_rows = rows[start:end] if start < total_count else []
        payload = {
            "action": action,
            "status": "success",
            "count": len(batch_rows),
            "total_count": total_count,
            "batch_count": batch_count,
            "batch_index": idx,
            "batch_size": size,
            "source": source_suffix,
            "results": batch_rows,
        }
        if batch_count > 1:
            payload["message"] = (
                f"Call with {batch_index_param}=0..{batch_count - 1} to read all batches."
            )
        return payload

    return {
        "action": action,
        "status": "success",
        "count": total_count,
        "source": source_suffix,
        "results": rows,
    }


def _safe_int(value: Any, default: int, *, minimum: int = 0) -> int:
    """Best-effort int parsing with lower bound."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _batch_count(total_items: int, batch_size: int) -> int:
    """Compute number of batches for fixed-size slicing."""
    if total_items <= 0:
        return 0
    return (total_items + batch_size - 1) // batch_size


def _slice_rows(rows: list[Any], *, batch_index: int, batch_size: int) -> list[Any]:
    """Return one batch slice; out-of-range returns empty list."""
    start = batch_index * batch_size
    end = start + batch_size
    if start >= len(rows):
        return []
    return rows[start:end]


def build_chunked_action_error_payload(
    *,
    action: str,
    message: str,
    query: str | None = None,
    preview_results: list[Any] | None = None,
    results: list[Any] | None = None,
    status: str = "error",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized action-scoped error payload for chunked workflows."""
    payload: dict[str, Any] = {
        "action": action,
        "status": status,
        "message": message,
    }
    if query is not None:
        payload["query"] = query
    if preview_results is not None:
        payload["preview_results"] = list(preview_results)
    if results is not None:
        payload["results"] = list(results)
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def build_chunked_unavailable_payload(
    *,
    message: str,
    query: str | None = None,
    action: str | None = None,
    results: list[Any] | None = None,
    status: str = "unavailable",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized unavailable payload for chunked workflows."""
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "results": list(results or []),
    }
    if query is not None:
        payload["query"] = query
    normalized_action = (action or "").strip()
    if normalized_action:
        payload["action"] = normalized_action
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def build_chunked_dispatch_error_payload(
    *,
    action: str,
    dispatch_result: Mapping[str, Any] | None,
    fallback_message: str = "chunked action dispatch failed",
    status: str = "error",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert dispatch failure output into a normalized action error payload."""
    message = fallback_message
    if isinstance(dispatch_result, Mapping):
        dispatch_error = dispatch_result.get("error")
        if dispatch_error:
            message = str(dispatch_error)
    return build_chunked_action_error_payload(
        action=action,
        message=str(message),
        status=status,
        extra=extra,
    )


def build_chunked_workflow_error_payload(
    *,
    error: str,
    workflow_type: str,
    success: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized workflow-level error payload for chunked engines."""
    payload: dict[str, Any] = {
        "success": bool(success),
        "error": str(error),
        "workflow_type": workflow_type,
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def create_chunked_lazy_start_payload(
    *,
    query: str,
    batch_size: Any,
    max_items: Any,
    preview_results: list[Any],
    status: str,
    state: dict[str, Any],
    persist_state: Callable[[str, dict[str, Any]], None],
    session_id_factory: Callable[[], str],
    action: str = "start",
    message_template: str = (
        "Call action=batch with session_id={session_id} and "
        "batch_index=0..{max_index} to read each chunk."
    ),
) -> dict[str, Any]:
    """Create+persist lazy chunked start state and return normalized start payload."""
    size = _safe_int(batch_size, 5, minimum=1)
    total_items = max(size, _safe_int(max_items, size, minimum=0))
    total_batches = _batch_count(total_items, size)
    sid = session_id_factory()
    persist_state(sid, state)
    return {
        "query": query,
        "action": action,
        "session_id": sid,
        "batch_count": total_batches,
        "preview_results": preview_results,
        "status": status,
        "message": message_template.format(session_id=sid, max_index=total_batches - 1),
    }


def build_chunked_session_store_adapters(
    store: ChunkedSessionStore,
) -> tuple[
    Callable[[str], dict[str, Any] | None],
    Callable[[str], tuple[ChunkedSession, dict[str, Any]] | None],
    Callable[[ChunkedSession, dict[str, Any]], None],
]:
    """
    Build normalized state adapters from ChunkedSessionStore for chunked runners.

    Returns:
    - load_metadata_state(workflow_id) -> dict | None
    - load_session_state(session_id) -> (ChunkedSession, dict) | None
    - save_session_state(session, state) -> None
    """

    def _load_metadata_state(workflow_id: str) -> dict[str, Any] | None:
        loaded = store.load(workflow_id)
        if not loaded:
            return None
        _session, loaded_state = loaded
        if not isinstance(loaded_state, dict):
            return None
        return loaded_state

    def _load_session_state(session_id: str) -> tuple[ChunkedSession, dict[str, Any]] | None:
        loaded = store.load(session_id)
        if not loaded:
            return None
        session, state = loaded
        return session, (state if isinstance(state, dict) else {})

    def _save_session_state(session: ChunkedSession, state: dict[str, Any]) -> None:
        store.save(session, metadata=state)

    return _load_metadata_state, _load_session_state, _save_session_state


def persist_chunked_lazy_start_state(
    *,
    store: ChunkedSessionStore,
    session_id: str,
    state: dict[str, Any],
    placeholder_batch: str = "",
    placeholder_batch_size: int = 1,
    placeholder_total_chars: int = 0,
) -> None:
    """
    Persist lazy-start state with placeholder chunked session content.

    Used by start actions that only store metadata and lazily fetch rows on first
    batch call.
    """
    store.save(
        ChunkedSession(
            session_id=session_id,
            batches=[placeholder_batch],
            batch_size=placeholder_batch_size,
            total_chars=placeholder_total_chars,
        ),
        metadata=state,
    )


async def run_chunked_full_document_action(
    *,
    source: str,
    list_all_entries: Callable[[str], Awaitable[list[dict[str, Any]]]],
    batch_size: Any,
    batch_index: Any,
    action: str = "full_document",
    batch_index_param: str = "full_document_batch_index",
    extra_payload_factory: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """
    Execute full-document list_all retrieval with normalized payload/error shape.
    """
    source_suffix = normalize_full_document_source(source)
    try:
        entries = await list_all_entries(source_suffix)
    except Exception as exc:
        return build_chunked_action_error_payload(
            action=action,
            message=str(exc),
            results=[],
        )

    matched = collect_full_document_rows(
        entries if isinstance(entries, list) else [],
        source=source_suffix,
    )
    payload = build_full_document_payload(
        rows=matched,
        source=source_suffix,
        batch_size=batch_size,
        batch_index=batch_index,
        action=action,
        batch_index_param=batch_index_param,
    )

    if extra_payload_factory is not None:
        try:
            extra = extra_payload_factory(source_suffix)
        except Exception:
            extra = None
        if isinstance(extra, dict) and extra:
            payload.update(extra)

    return payload


async def run_chunked_cached_batch_action(
    *,
    session_id: str,
    batch_index: Any,
    load_session_state: Callable[[str], tuple[Any, dict[str, Any]] | None],
    save_session_state: Callable[[Any, dict[str, Any]], None],
    fetch_rows: Callable[[dict[str, Any]], Awaitable[list[Any]]],
    action: str = "batch",
    batch_size_key: str = "batch_size",
    max_items_key: str = "max_chunks",
    cache_ready_key: str = "cached_results_ready",
    cache_rows_key: str = "cached_results",
    default_batch_size: int = 5,
    default_max_items: int = 30,
    missing_session_template: str = "session_id not found: {session_id}",
    invalid_batch_template: str = "batch_index must be 0..{max_index}",
    fetch_timeout_message: str = "Batch fetch timed out.",
) -> dict[str, Any]:
    """
    Handle action=batch with lazy cached rows persisted in session metadata.

    Flow:
    - Load session state
    - Validate batch_index against computed batch_count(max_items, batch_size)
    - If cache not ready, fetch full rows once and persist to state
    - Slice one batch and return normalized payload
    """
    sid = (session_id or "").strip()
    loaded = load_session_state(sid)
    if not loaded:
        return build_chunked_action_error_payload(
            action=action,
            message=missing_session_template.format(session_id=sid),
        )

    session, state = loaded
    if not isinstance(state, dict):
        state = {}

    size = _safe_int(state.get(batch_size_key), default_batch_size, minimum=1)
    declared_total_items = _safe_int(state.get(max_items_key), default_max_items, minimum=0)
    declared_total_batches = _batch_count(declared_total_items, size)
    idx = _safe_int(batch_index, -1, minimum=-1)

    if idx < 0 or idx >= declared_total_batches:
        return build_chunked_action_error_payload(
            action=action,
            message=invalid_batch_template.format(max_index=declared_total_batches - 1),
            extra={
                "session_id": sid,
                "batch_index": idx,
                "batch_count": declared_total_batches,
            },
        )

    ready = bool(state.get(cache_ready_key))
    cached_rows = state.get(cache_rows_key)
    if ready and isinstance(cached_rows, list):
        all_rows = cached_rows
        if declared_total_items > 0 and len(all_rows) > declared_total_items:
            all_rows = all_rows[:declared_total_items]
            state[cache_rows_key] = all_rows
            state[max_items_key] = declared_total_items
            save_session_state(session, state)
    else:
        try:
            fetched_rows = await fetch_rows(state)
        except TimeoutError:
            return build_chunked_action_error_payload(
                action=action,
                message=fetch_timeout_message,
                extra={
                    "session_id": sid,
                    "batch_index": idx,
                },
            )
        all_rows = fetched_rows if isinstance(fetched_rows, list) else []
        if declared_total_items > 0:
            all_rows = all_rows[:declared_total_items]
            state[max_items_key] = min(declared_total_items, len(all_rows))
        else:
            state[max_items_key] = len(all_rows)
        state[cache_ready_key] = True
        state[cache_rows_key] = all_rows
        save_session_state(session, state)

    effective_total_items = (
        min(declared_total_items, len(all_rows)) if declared_total_items > 0 else len(all_rows)
    )
    total_batches = _batch_count(effective_total_items, size)
    if idx >= total_batches:
        return build_chunked_action_error_payload(
            action=action,
            message=invalid_batch_template.format(max_index=total_batches - 1),
            extra={
                "session_id": sid,
                "batch_index": idx,
                "batch_count": total_batches,
            },
        )

    return {
        "action": action,
        "session_id": sid,
        "batch_index": idx,
        "batch_count": total_batches,
        "batch": _slice_rows(all_rows, batch_index=idx, batch_size=size),
        "status": "success",
    }


async def run_chunked_preview_action(
    *,
    query: str,
    run_preview: Callable[[], Awaitable[Any]],
    parse_preview_payload: Callable[[Any], dict[str, Any]],
    timeout_seconds: float,
    action: str = "preview",
    success_message: str,
    timeout_message: str,
) -> dict[str, Any]:
    """Execute preview call with timeout + normalized payload shape."""
    try:
        out = await asyncio.wait_for(run_preview(), timeout=float(timeout_seconds))
    except TimeoutError:
        return build_chunked_action_error_payload(
            action=action,
            message=timeout_message,
            query=query,
            preview_results=[],
        )

    try:
        data = parse_preview_payload(out)
    except Exception as exc:
        return build_chunked_action_error_payload(
            action=action,
            message=str(exc),
            query=query,
            preview_results=[],
        )

    return {
        "query": query,
        "action": action,
        "preview_results": data.get("results", []),
        "status": data.get("status", "success"),
        "message": success_message,
    }


async def run_chunked_auto_complete(
    workflow_type: str,
    run_start: Callable[[], Any],
    run_step: Callable[[dict[str, Any]], Any],
    run_synthesize: Callable[[dict[str, Any]], Any],
    *,
    queue_key: str = "queue",
) -> dict[str, Any]:
    """
    Run full chunked workflow in one call (start -> step x N -> synthesize).

    Use when action=start to avoid burning agent rounds. Each step would otherwise
    count as one round; N+2 rounds for N chunks. This uses 1 round.

    Uses run_with_heartbeat to avoid MCP timeout during long runs.
    """

    engine = ChunkedWorkflowEngine(
        workflow_type=workflow_type,
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key=queue_key,
    )
    return await engine.run_auto_complete()


async def run_chunked_action_dispatch(
    *,
    action: str,
    session_id: str,
    workflow_type: str,
    load_state: Callable[[str], dict[str, Any] | None],
    on_start: Callable[[], Any] | None = None,
    on_shard: Callable[[str, dict[str, Any]], Any] | None = None,
    on_synthesize: Callable[[str, dict[str, Any]], Any] | None = None,
    session_required_error: str = "session_id required for action=shard and action=synthesize",
    session_missing_error: str = "No state found for this session_id; run action=start first.",
    unknown_action_template: str = "Unknown action: {action}. Use start | shard | synthesize.",
    action_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Dispatch action=start|shard|synthesize with shared guardrails.

    Common behavior:
    - start: no session required
    - shard/synthesize: require session_id and existing persisted state
    - unknown action: standardized error payload
    """
    alias_map = {"chunk": "shard"}
    if action_aliases:
        alias_map.update(action_aliases)
    normalized_action = normalize_chunked_action_name(action, action_aliases=alias_map)

    if normalized_action == "start":
        if on_start is None:
            return build_chunked_workflow_error_payload(
                error=unknown_action_template.format(action=normalized_action),
                workflow_type=workflow_type,
            )
        out = on_start()
        return await out if asyncio.iscoroutine(out) else out

    sid = (session_id or "").strip()
    if not sid:
        return build_chunked_workflow_error_payload(
            error=session_required_error,
            workflow_type=workflow_type,
        )

    loaded = load_state(sid)
    if not loaded:
        try:
            missing_error = session_missing_error.format(session_id=sid)
        except Exception:
            missing_error = session_missing_error
        return build_chunked_workflow_error_payload(
            error=missing_error,
            workflow_type=workflow_type,
        )

    if normalized_action == "shard" and on_shard is not None:
        out = on_shard(sid, loaded)
        return await out if asyncio.iscoroutine(out) else out

    if normalized_action == "synthesize" and on_synthesize is not None:
        out = on_synthesize(sid, loaded)
        return await out if asyncio.iscoroutine(out) else out

    return build_chunked_workflow_error_payload(
        error=unknown_action_template.format(action=normalized_action),
        workflow_type=workflow_type,
    )


async def run_chunked_lazy_start_batch_dispatch(
    *,
    action: str,
    session_id: str,
    batch_index: Any,
    workflow_type: str,
    load_state: Callable[[str], dict[str, Any] | None],
    on_start: Callable[[], Any],
    load_session_state: Callable[[str], tuple[Any, dict[str, Any]] | None],
    save_session_state: Callable[[Any, dict[str, Any]], None],
    fetch_rows: Callable[[dict[str, Any]], Awaitable[list[Any]]],
    batch_action: str = "batch",
    batch_size_key: str = "batch_size",
    max_items_key: str = "max_chunks",
    cache_ready_key: str = "cached_results_ready",
    cache_rows_key: str = "cached_results",
    default_batch_size: int = 5,
    default_max_items: int = 30,
    missing_session_template: str = "session_id not found: {session_id}",
    invalid_batch_template: str = "batch_index must be 0..{max_index}",
    fetch_timeout_message: str = "Batch fetch timed out.",
    session_required_error: str = "session_id required for action=batch",
    session_missing_error: str = "session_id not found: {session_id}",
    action_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Dispatch start/batch actions for lazy cached chunk reads."""

    async def _on_shard(sid: str, loaded_state: dict[str, Any]) -> dict[str, Any]:
        del loaded_state
        return await run_chunked_cached_batch_action(
            session_id=sid,
            batch_index=batch_index,
            load_session_state=load_session_state,
            save_session_state=save_session_state,
            fetch_rows=fetch_rows,
            action=batch_action,
            batch_size_key=batch_size_key,
            max_items_key=max_items_key,
            cache_ready_key=cache_ready_key,
            cache_rows_key=cache_rows_key,
            default_batch_size=default_batch_size,
            default_max_items=default_max_items,
            missing_session_template=missing_session_template,
            invalid_batch_template=invalid_batch_template,
            fetch_timeout_message=fetch_timeout_message,
        )

    alias_map = {batch_action: "shard", "fetch": "start"}
    if action_aliases:
        alias_map.update(action_aliases)

    return await run_chunked_action_dispatch(
        action=action,
        session_id=session_id,
        workflow_type=workflow_type,
        load_state=load_state,
        on_start=on_start,
        on_shard=_on_shard,
        session_required_error=session_required_error,
        session_missing_error=session_missing_error,
        action_aliases=alias_map,
    )


async def run_chunked_step(
    workflow_type: str,
    session_id: str,
    action: str,
    run_start: Callable[[], Any],
    run_step: Callable[[dict[str, Any]], Any],
    run_synthesize: Callable[[dict[str, Any]], Any],
    *,
    queue_key: str = "queue",
    auto_complete: bool = True,
) -> dict[str, Any]:
    """
    Execute one step of a chunked workflow and persist state.

    When auto_complete=True (default) and action=start: runs full workflow in one
    call and returns final result. Avoids N+2 agent rounds.

    Actions:
    - start: run run_start() (e.g. setup + plan). If auto_complete: run full workflow.
    - shard/chunk: load state, run run_step(state) (process one chunk), save, return progress.
    - synthesize: load state, run run_synthesize(state), return final result.

    Args:
        workflow_type: Key for persistence (e.g. "research_chunked", "recall_chunked").
        session_id: Session id (from start response); required for shard and synthesize.
        action: "start" | "shard" | "synthesize" (or "chunk" as alias for shard).
        run_start: Callable that returns initial state (with queue, etc.). Async or sync.
        run_step: Callable(state) -> updated state. Async or sync.
        run_synthesize: Callable(state) -> state with final result. Async or sync.
        queue_key: State key for the chunk queue (default "queue"; use "shards_queue" for researcher).
        auto_complete: If True and action=start, run full workflow in one call (default True).

    Returns:
        Dict with success, session_id (for start), next_action hint, or result payload.
    """
    engine = ChunkedWorkflowEngine(
        workflow_type=workflow_type,
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key=queue_key,
    )
    return await engine.run_step(
        session_id=session_id,
        action=action,
        auto_complete=auto_complete,
    )


async def run_chunked_complete_from_session(
    workflow_type: str,
    session_id: str,
    run_start: Callable[[], Any],
    run_step: Callable[[dict[str, Any]], Any],
    run_synthesize: Callable[[dict[str, Any]], Any],
    *,
    queue_key: str = "queue",
    store: WorkflowStoreLike | None = None,
) -> dict[str, Any]:
    """Resume from persisted session and complete remaining chunks + synthesize."""
    engine = ChunkedWorkflowEngine(
        workflow_type=workflow_type,
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key=queue_key,
        store=store,
    )
    return await engine.run_complete_from_session(session_id)


async def run_chunked_parallel_selected[ResultT](
    selected_ids: list[str],
    process_selected: Callable[[str], Awaitable[ResultT]],
    *,
    id_key: str = "chunk_id",
    max_concurrent: int | None = None,
) -> list[ResultT]:
    """
    Run selected chunk ids in parallel as one level.

    Reusable for skills that expose action=shard with selectors (e.g. chunk_ids)
    and need bounded concurrency while preserving a simple API.
    """
    if not selected_ids:
        return []

    level = [({id_key: item_id}, idx + 1) for idx, item_id in enumerate(selected_ids)]

    async def _process(
        item: dict[str, Any],
        _item_id: int,
        _state: dict[str, Any],
    ) -> ResultT:
        value = str(item.get(id_key, "")).strip()
        return await process_selected(value)

    results = await run_parallel_levels(
        [level],
        _process,
        {},
        max_concurrent=max_concurrent,
    )
    return results


async def run_chunked_child_step(
    *,
    session_id: str,
    chunk_id: str,
    load_state: Callable[[str], dict[str, Any] | None],
    save_state: Callable[[str, dict[str, Any]], None],
    run_step: Callable[[dict[str, Any]], Any],
    build_child_id: Callable[[str, str], str],
    queue_key: str = "shards_queue",
    current_key: str = "current_shard",
    name_key: str = "name",
    error_key: str = "error",
    missing_state_error_template: str = "No chunk state found for {chunk_id}; run action=start first.",
) -> dict[str, Any]:
    """Run one child chunk state and persist it, with normalized status payload."""
    child_id = build_child_id(session_id, chunk_id)
    loaded = load_state(child_id)
    if not loaded:
        return {
            "success": False,
            "chunk_id": chunk_id,
            "status": "missing",
            "error": missing_state_error_template.format(chunk_id=chunk_id),
        }

    queue = loaded.get(queue_key, [])
    if not queue:
        current = loaded.get(current_key) or {}
        return {
            "success": True,
            "chunk_id": chunk_id,
            "chunk_processed": current.get(name_key, ""),
            "status": "already_done",
        }

    state_or_coro = run_step(loaded)
    state = await state_or_coro if asyncio.iscoroutine(state_or_coro) else state_or_coro
    if not isinstance(state, dict):
        return {
            "success": False,
            "chunk_id": chunk_id,
            "status": "error",
            "error": f"run_step must return dict state, got {type(state).__name__}",
        }
    if state.get(error_key):
        return {
            "success": False,
            "chunk_id": chunk_id,
            "status": "error",
            "error": str(state[error_key]),
        }

    save_state(child_id, state)
    current = state.get(current_key) or {}
    return {
        "success": True,
        "chunk_id": chunk_id,
        "chunk_processed": current.get(name_key, ""),
        "status": "processed",
    }


async def run_chunked_fanout_shard[ResultT](
    *,
    workflow_type: str,
    session_id: str,
    chunk_plan: list[dict[str, Any]],
    requested_chunk_ids: list[str],
    process_selected: Callable[[str], Awaitable[ResultT]],
    load_state: Callable[[str], dict[str, Any] | None],
    build_child_id: Callable[[str, str], str],
    id_key: str = "chunk_id",
    queue_key: str = "shards_queue",
    summaries_key: str = "shard_analyses",
    max_concurrent: int | None = None,
    next_action_pending: str = "Call action=shard with remaining chunk_ids",
    next_action_done: str = "Call action=synthesize with this session_id",
) -> dict[str, Any]:
    """
    Execute selected (or pending) fan-out chunk ids and return normalized progress payload.

    This is the common orchestration path for workflows that keep one master chunk plan
    and process child chunk states by id (for example, researcher action=shard).
    """
    selected_ids: list[str] = []
    for item_id in requested_chunk_ids:
        value = str(item_id).strip()
        if value and value not in selected_ids:
            selected_ids.append(value)

    valid_ids = {str(item.get(id_key, "")).strip() for item in chunk_plan}
    valid_ids.discard("")

    invalid_ids = [chunk_id for chunk_id in selected_ids if chunk_id not in valid_ids]
    if invalid_ids:
        return build_chunked_workflow_error_payload(
            error=f"Unknown chunk_id(s): {', '.join(invalid_ids)}",
            workflow_type=workflow_type,
        )

    if not selected_ids:
        progress = collect_chunk_progress(
            session_id=session_id,
            chunk_plan=chunk_plan,
            load_state=load_state,
            build_child_id=build_child_id,
            id_key=id_key,
            queue_key=queue_key,
            summaries_key=summaries_key,
        )
        selected_ids = progress["pending_chunk_ids"]
        if not selected_ids:
            return {
                "success": True,
                "session_id": session_id,
                "chunks_requested": 0,
                "chunk_results": [],
                "chunks_remaining": 0,
                "pending_chunk_ids": [],
                "completed_chunk_ids": progress["completed_chunk_ids"],
                "workflow_type": workflow_type,
                "next_action": next_action_done,
            }

    chunk_results = await run_chunked_parallel_selected(
        selected_ids,
        process_selected,
        id_key=id_key,
        max_concurrent=max_concurrent,
    )

    failed = [
        item for item in chunk_results if isinstance(item, dict) and item.get("success") is False
    ]

    progress = collect_chunk_progress(
        session_id=session_id,
        chunk_plan=chunk_plan,
        load_state=load_state,
        build_child_id=build_child_id,
        id_key=id_key,
        queue_key=queue_key,
        summaries_key=summaries_key,
    )
    pending = progress["pending_chunk_ids"]
    return {
        "success": not failed,
        "session_id": session_id,
        "chunks_requested": len(selected_ids),
        "chunk_results": chunk_results,
        "chunks_remaining": len(pending),
        "pending_chunk_ids": pending,
        "completed_chunk_ids": progress["completed_chunk_ids"],
        "workflow_type": workflow_type,
        "next_action": next_action_pending if pending else next_action_done,
    }


async def run_chunked_fanout_synthesize(
    *,
    workflow_type: str,
    session_id: str,
    loaded_state: dict[str, Any],
    chunk_plan: list[dict[str, Any]],
    run_synthesize: Callable[[dict[str, Any]], Any],
    load_state: Callable[[str], dict[str, Any] | None],
    build_child_id: Callable[[str, str], str],
    id_key: str = "chunk_id",
    queue_key: str = "shards_queue",
    summaries_key: str = "shard_analyses",
    error_key: str = "error",
    pending_error_message: str = (
        "Some chunks are not finished yet; run action=shard for pending_chunk_ids."
    ),
) -> dict[str, Any]:
    """
    Synthesize fan-out child chunks with pending guard and normalized final payload.

    This helper enforces that all child chunks are completed before synthesis, then
    runs synthesize with ordered per-chunk summaries.
    """
    progress = collect_chunk_progress(
        session_id=session_id,
        chunk_plan=chunk_plan,
        load_state=load_state,
        build_child_id=build_child_id,
        id_key=id_key,
        queue_key=queue_key,
        summaries_key=summaries_key,
    )
    pending = progress["pending_chunk_ids"]
    if pending:
        return build_chunked_workflow_error_payload(
            error=pending_error_message,
            workflow_type=workflow_type,
            extra={
                "session_id": session_id,
                "pending_chunk_ids": pending,
            },
        )

    synth_state = {
        **loaded_state,
        queue_key: [],
        summaries_key: progress["ordered_summaries"],
    }
    state_or_coro = run_synthesize(synth_state)
    state = await state_or_coro if asyncio.iscoroutine(state_or_coro) else state_or_coro
    step_result = (
        {"success": True, "state": state}
        if isinstance(state, dict)
        else {
            "success": True,
            "result": state,
        }
    )
    return build_summary_payload_from_chunked_step_result(
        step_result,
        workflow_type=workflow_type,
        session_id=session_id,
        state_error_key=error_key,
    )
