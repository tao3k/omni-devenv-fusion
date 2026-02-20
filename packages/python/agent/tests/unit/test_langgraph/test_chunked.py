"""Tests for omni.langgraph.chunked (normalize, runner, state)."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest

from omni.langgraph.chunked import (
    DEFAULT_MAX_PER_CHUNK,
    DEFAULT_MAX_TOTAL,
    DEFAULT_MIN_TO_MERGE,
    ChunkConfig,
    ChunkedWorkflowEngine,
    build_child_work_items,
    build_chunk_plan_from_queue,
    build_chunked_action_error_payload,
    build_chunked_dispatch_error_payload,
    build_chunked_session_store_adapters,
    build_chunked_unavailable_payload,
    build_chunked_workflow_error_payload,
    build_full_document_payload,
    build_summary_payload_from_chunked_result,
    build_summary_payload_from_chunked_step_result,
    build_summary_payload_from_state,
    collect_chunk_progress,
    collect_full_document_rows,
    create_chunked_lazy_start_payload,
    extract_chunk_plan,
    extract_state_or_scalar_result,
    normalize_chunks,
    normalize_full_document_source,
    normalize_selected_ids,
    persist_chunked_lazy_start_state,
    run_chunked_action_dispatch,
    run_chunked_auto_complete,
    run_chunked_cached_batch_action,
    run_chunked_child_step,
    run_chunked_complete_from_session,
    run_chunked_fanout_shard,
    run_chunked_fanout_synthesize,
    run_chunked_full_document_action,
    run_chunked_lazy_start_batch_dispatch,
    run_chunked_parallel_selected,
    run_chunked_preview_action,
    run_chunked_step,
)


def test_normalize_chunks_empty():
    assert normalize_chunks([]) == []
    assert normalize_chunks([], ChunkConfig()) == []


def test_normalize_chunks_under_limit_unchanged():
    items = [
        {"name": "A", "targets": ["a.py", "b.py"], "description": "A"},
        {"name": "B", "targets": ["c.py"], "description": "B"},
    ]
    config = ChunkConfig(max_per_chunk=5, max_total=10, min_to_merge=0)
    out = normalize_chunks(items, config)
    assert len(out) == 2
    assert [len(x["targets"]) for x in out] == [2, 1]


def test_normalize_chunks_splits_oversized():
    items = [
        {"name": "Big", "targets": ["a", "b", "c", "d", "e", "f", "g"], "description": "Big"},
    ]
    config = ChunkConfig(max_per_chunk=3, max_total=20, min_to_merge=1)
    out = normalize_chunks(items, config)
    assert len(out) == 3
    assert sum(len(x["targets"]) for x in out) == 7
    assert all(len(x["targets"]) <= 3 for x in out)


def test_normalize_chunks_caps_total():
    items = [
        {"name": "X", "targets": ["a"] * 10, "description": "X"},
        {"name": "Y", "targets": ["b"] * 10, "description": "Y"},
    ]
    config = ChunkConfig(max_per_chunk=10, max_total=12, min_to_merge=0)
    out = normalize_chunks(items, config)
    total = sum(len(x["targets"]) for x in out)
    assert total <= 12


def test_chunk_config_defaults():
    c = ChunkConfig()
    assert c.max_per_chunk == DEFAULT_MAX_PER_CHUNK
    assert c.max_total == DEFAULT_MAX_TOTAL
    assert c.min_to_merge == DEFAULT_MIN_TO_MERGE


def test_full_document_helpers_normalize_collect_and_build_payload():
    """Full-document helpers should normalize source, dedupe rows, and shape batch payload."""
    source_suffix = normalize_full_document_source(" https://arxiv.org/pdf/2601.03192 ")
    assert source_suffix == "2601.03192"

    rows = collect_full_document_rows(
        [
            {"content": "chunk0", "metadata": {"source": "/x/2601.03192.pdf", "chunk_index": 0}},
            {"content": "chunk1", "metadata": {"source": "/x/2601.03192.pdf", "chunk_index": 1}},
            {"content": "dup1", "metadata": {"source": "/x/2601.03192.pdf", "chunk_index": 1}},
            {
                "content": "other",
                "metadata": {"source": "/x/other.pdf", "chunk_index": 99},
            },
        ],
        source="2601.03192.pdf",
    )
    assert [r["chunk_index"] for r in rows] == [0, 1]
    assert [r["content"] for r in rows] == ["chunk0", "chunk1"]

    payload = build_full_document_payload(
        rows=rows,
        source="2601.03192.pdf",
        batch_size=1,
        batch_index=1,
    )
    assert payload["action"] == "full_document"
    assert payload["status"] == "success"
    assert payload["total_count"] == 2
    assert payload["batch_count"] == 2
    assert payload["batch_index"] == 1
    assert payload["count"] == 1
    assert payload["results"][0]["content"] == "chunk1"
    assert "full_document_batch_index" in payload.get("message", "")


def test_create_chunked_lazy_start_payload_persists_and_shapes_response():
    """Start helper should persist state and return normalized start payload."""
    persisted: dict[str, dict[str, Any]] = {}

    def _persist(session_id: str, state: dict[str, Any]) -> None:
        persisted[session_id] = dict(state)

    payload = create_chunked_lazy_start_payload(
        query="search",
        batch_size=2,
        max_items=4,
        preview_results=[{"content": "preview"}],
        status="success",
        state={"query": "search", "cached_results_ready": False, "cached_results": []},
        persist_state=_persist,
        session_id_factory=lambda: "sid-1",
        action="start",
    )

    assert payload == {
        "query": "search",
        "action": "start",
        "session_id": "sid-1",
        "batch_count": 2,
        "preview_results": [{"content": "preview"}],
        "status": "success",
        "message": "Call action=batch with session_id=sid-1 and batch_index=0..1 to read each chunk.",
    }
    assert persisted["sid-1"]["query"] == "search"


def test_build_chunked_session_store_adapters_and_lazy_start_persist():
    """Store adapter helpers should normalize metadata/session load/save behavior."""
    saved: dict[str, tuple[Any, dict[str, Any] | None]] = {}

    class _FakeStore:
        def load(self, session_id: str) -> tuple[Any, dict[str, Any] | None] | None:
            return saved.get(session_id)

        def save(self, session: Any, *, metadata: dict[str, Any] | None = None) -> None:
            saved[session.session_id] = (session, metadata)

    store = _FakeStore()
    load_state, load_session, save_session = build_chunked_session_store_adapters(store)  # type: ignore[arg-type]
    assert load_state("missing") is None

    persist_chunked_lazy_start_state(
        store=store,  # type: ignore[arg-type]
        session_id="sid-1",
        state={"query": "x", "cached_results_ready": False},
    )
    metadata = load_state("sid-1")
    assert metadata == {"query": "x", "cached_results_ready": False}

    loaded = load_session("sid-1")
    assert loaded is not None
    session, state = loaded
    assert session.session_id == "sid-1"
    assert session.batch_size == 1
    assert session.batches == [""]
    assert state["query"] == "x"

    state["cached_results_ready"] = True
    save_session(session, state)
    assert load_state("sid-1") == {"query": "x", "cached_results_ready": True}


@pytest.mark.asyncio
async def test_run_chunked_full_document_action_handles_success_error_and_extra_payload():
    """Common full-document action helper should normalize result and error payloads."""

    async def _list_ok(source_suffix: str) -> list[dict[str, Any]]:
        assert source_suffix == "doc.pdf"
        return [
            {"content": "chunk0", "metadata": {"source": "/x/doc.pdf", "chunk_index": 0}},
            {"content": "chunk1", "metadata": {"source": "/x/doc.pdf", "chunk_index": 1}},
            {"content": "dup1", "metadata": {"source": "/x/doc.pdf", "chunk_index": 1}},
        ]

    payload = await run_chunked_full_document_action(
        source="tmp/doc.pdf",
        list_all_entries=_list_ok,
        batch_size=1,
        batch_index=1,
        extra_payload_factory=lambda source_suffix: {"debug_source": source_suffix},
    )
    assert payload["status"] == "success"
    assert payload["action"] == "full_document"
    assert payload["source"] == "doc.pdf"
    assert payload["total_count"] == 2
    assert payload["batch_index"] == 1
    assert payload["count"] == 1
    assert payload["results"][0]["content"] == "chunk1"
    assert payload["debug_source"] == "doc.pdf"

    async def _list_error(_source_suffix: str) -> list[dict[str, Any]]:
        raise RuntimeError("list_all failed")

    error = await run_chunked_full_document_action(
        source="doc.pdf",
        list_all_entries=_list_error,
        batch_size=10,
        batch_index=0,
    )
    assert error == {
        "action": "full_document",
        "status": "error",
        "message": "list_all failed",
        "results": [],
    }


@pytest.mark.asyncio
async def test_run_chunked_preview_action_success_and_timeout():
    """Preview action helper should produce consistent success/timeout payloads."""

    async def _success_preview():
        return {"results": [{"content": "x"}], "status": "success"}

    success = await run_chunked_preview_action(
        query="q",
        run_preview=_success_preview,
        parse_preview_payload=lambda out: out,
        timeout_seconds=0.2,
        action="preview",
        success_message="ok",
        timeout_message="timeout",
    )
    assert success == {
        "query": "q",
        "action": "preview",
        "preview_results": [{"content": "x"}],
        "status": "success",
        "message": "ok",
    }

    async def _timeout_preview():
        await asyncio.sleep(0.05)
        return {"results": []}

    timeout = await run_chunked_preview_action(
        query="q",
        run_preview=_timeout_preview,
        parse_preview_payload=lambda out: out,
        timeout_seconds=0.001,
        action="preview",
        success_message="ok",
        timeout_message="timeout",
    )
    assert timeout == {
        "query": "q",
        "action": "preview",
        "status": "error",
        "message": "timeout",
        "preview_results": [],
    }


def test_chunked_payload_builders_normalize_action_error_and_unavailable():
    action_error = build_chunked_action_error_payload(
        action="start",
        message="query required",
        query="q",
        preview_results=[],
        extra={"debug": True},
    )
    assert action_error == {
        "action": "start",
        "status": "error",
        "message": "query required",
        "query": "q",
        "preview_results": [],
        "debug": True,
    }

    unavailable = build_chunked_unavailable_payload(
        query="q",
        action="full_document",
        message="store unavailable",
    )
    assert unavailable == {
        "query": "q",
        "action": "full_document",
        "status": "unavailable",
        "message": "store unavailable",
        "results": [],
    }


def test_build_chunked_dispatch_error_payload_uses_dispatch_error_then_fallback():
    with_error = build_chunked_dispatch_error_payload(
        action="batch",
        dispatch_result={"success": False, "error": "session not found"},
    )
    assert with_error == {
        "action": "batch",
        "status": "error",
        "message": "session not found",
    }

    fallback = build_chunked_dispatch_error_payload(
        action="start",
        dispatch_result={"success": False},
        fallback_message="dispatch failed",
    )
    assert fallback == {
        "action": "start",
        "status": "error",
        "message": "dispatch failed",
    }


def test_build_chunked_workflow_error_payload_normalizes_error_shape():
    payload = build_chunked_workflow_error_payload(
        error="No state found",
        workflow_type="research_chunked",
    )
    assert payload == {
        "success": False,
        "error": "No state found",
        "workflow_type": "research_chunked",
    }

    with_extra = build_chunked_workflow_error_payload(
        error="workflow failed",
        workflow_type="research",
        extra={"workflow_id": "wf-1", "steps": 3},
    )
    assert with_extra == {
        "success": False,
        "error": "workflow failed",
        "workflow_type": "research",
        "workflow_id": "wf-1",
        "steps": 3,
    }


@pytest.mark.asyncio
async def test_run_chunked_cached_batch_action_reuses_cached_rows_and_slices():
    """Cached batch helper should fetch once then reuse cached rows across calls."""
    session = object()
    store: dict[str, tuple[object, dict[str, Any]]] = {
        "sid-1": (
            session,
            {
                "batch_size": 2,
                "max_chunks": 4,
                "cached_results_ready": False,
                "cached_results": [],
            },
        )
    }
    fetch_calls = {"count": 0}
    save_calls = {"count": 0}

    def _load_state(session_id: str) -> tuple[object, dict[str, Any]] | None:
        return store.get(session_id)

    def _save_state(saved_session: object, state: dict[str, Any]) -> None:
        assert saved_session is session
        save_calls["count"] += 1
        store["sid-1"] = (saved_session, state)

    async def _fetch_rows(_state: dict[str, Any]) -> list[Any]:
        fetch_calls["count"] += 1
        return ["a", "b", "c", "d"]

    first = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=0,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )
    second = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=1,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )

    assert first["status"] == "success"
    assert first["batch"] == ["a", "b"]
    assert second["status"] == "success"
    assert second["batch"] == ["c", "d"]
    assert fetch_calls["count"] == 1
    assert save_calls["count"] == 1


@pytest.mark.asyncio
async def test_run_chunked_cached_batch_action_error_paths():
    """Cached batch helper should return normalized missing/index/timeout errors."""

    def _load_missing(_session_id: str):
        return None

    async def _fetch_never(_state: dict[str, Any]) -> list[Any]:
        return []

    missing = await run_chunked_cached_batch_action(
        session_id="sid-missing",
        batch_index=0,
        load_session_state=_load_missing,
        save_session_state=lambda _session, _state: None,
        fetch_rows=_fetch_never,
        action="batch",
        missing_session_template="session_id not found: {session_id}",
    )
    assert missing == {
        "action": "batch",
        "status": "error",
        "message": "session_id not found: sid-missing",
    }

    session = object()
    invalid_state = (
        session,
        {"batch_size": 2, "max_chunks": 4, "cached_results_ready": True, "cached_results": []},
    )

    invalid = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=9,
        load_session_state=lambda _sid: invalid_state,
        save_session_state=lambda _session, _state: None,
        fetch_rows=_fetch_never,
        action="batch",
    )
    assert invalid["status"] == "error"
    assert invalid["batch_count"] == 2
    assert "0..1" in invalid["message"]

    timeout_state = (
        session,
        {"batch_size": 2, "max_chunks": 4, "cached_results_ready": False, "cached_results": []},
    )

    async def _fetch_timeout(_state: dict[str, Any]) -> list[Any]:
        raise TimeoutError

    timeout = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=0,
        load_session_state=lambda _sid: timeout_state,
        save_session_state=lambda _session, _state: None,
        fetch_rows=_fetch_timeout,
        action="batch",
        fetch_timeout_message="Recall timed out for this batch.",
    )
    assert timeout == {
        "action": "batch",
        "session_id": "sid-1",
        "batch_index": 0,
        "status": "error",
        "message": "Recall timed out for this batch.",
    }


@pytest.mark.asyncio
async def test_run_chunked_cached_batch_action_caps_cached_rows_to_max_items():
    """Fetched rows should be capped by configured max items before caching/slicing."""
    session = object()
    store: dict[str, tuple[object, dict[str, Any]]] = {
        "sid-1": (
            session,
            {
                "batch_size": 1,
                "max_chunks": 2,
                "cached_results_ready": False,
                "cached_results": [],
            },
        )
    }
    fetch_calls = {"count": 0}

    def _load_state(session_id: str) -> tuple[object, dict[str, Any]] | None:
        return store.get(session_id)

    def _save_state(saved_session: object, state: dict[str, Any]) -> None:
        assert saved_session is session
        store["sid-1"] = (saved_session, state)

    async def _fetch_rows(_state: dict[str, Any]) -> list[Any]:
        fetch_calls["count"] += 1
        return ["a", "b", "c", "d"]

    first = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=0,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )
    second = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=1,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert first["batch_count"] == 2
    assert second["batch_count"] == 2
    assert first["batch"] == ["a"]
    assert second["batch"] == ["b"]
    assert fetch_calls["count"] == 1
    assert store["sid-1"][1]["cached_results"] == ["a", "b"]


@pytest.mark.asyncio
async def test_run_chunked_cached_batch_action_recomputes_batch_count_from_fetched_rows():
    """Batch_count should shrink to fetched rows and reject stale high batch indexes."""
    session = object()
    state = {
        "batch_size": 2,
        "max_chunks": 5,
        "cached_results_ready": False,
        "cached_results": [],
    }

    def _load_state(_session_id: str) -> tuple[object, dict[str, Any]] | None:
        return session, state

    def _save_state(_saved_session: object, saved_state: dict[str, Any]) -> None:
        state.update(saved_state)

    async def _fetch_rows(_state: dict[str, Any]) -> list[Any]:
        return ["a", "b", "c"]

    ok = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=1,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )
    invalid = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=2,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )

    assert ok["status"] == "success"
    assert ok["batch_count"] == 2
    assert ok["batch"] == ["c"]
    assert invalid["status"] == "error"
    assert invalid["batch_count"] == 2
    assert "0..1" in invalid["message"]


@pytest.mark.asyncio
async def test_run_chunked_cached_batch_action_trims_oversized_ready_cache():
    """Ready cache should be trimmed to max_items to auto-repair stale oversized sessions."""
    session = object()
    state = {
        "batch_size": 2,
        "max_chunks": 2,
        "cached_results_ready": True,
        "cached_results": ["a", "b", "c"],
    }
    save_calls = {"count": 0}

    def _load_state(_session_id: str) -> tuple[object, dict[str, Any]] | None:
        return session, state

    def _save_state(_saved_session: object, saved_state: dict[str, Any]) -> None:
        save_calls["count"] += 1
        state.update(saved_state)

    async def _fetch_rows(_state: dict[str, Any]) -> list[Any]:
        raise AssertionError("fetch_rows should not run when cache is ready")

    out = await run_chunked_cached_batch_action(
        session_id="sid-1",
        batch_index=0,
        load_session_state=_load_state,
        save_session_state=_save_state,
        fetch_rows=_fetch_rows,
        action="batch",
    )

    assert out["status"] == "success"
    assert out["batch_count"] == 1
    assert out["batch"] == ["a", "b"]
    assert state["cached_results"] == ["a", "b"]
    assert save_calls["count"] == 1


def test_chunk_plan_helpers_build_extract_and_normalize_selected_ids():
    queue = [
        {"name": "A", "targets": ["a.py"], "description": "A"},
        {"name": "B", "targets": ["b.py"], "description": "B"},
    ]
    plan = build_chunk_plan_from_queue(queue)
    assert [item["chunk_id"] for item in plan] == ["c1", "c2"]

    extracted = extract_chunk_plan({"chunk_plan": plan})
    assert [item["chunk_id"] for item in extracted] == ["c1", "c2"]

    selected = normalize_selected_ids("c1", ["c2", "c1", ""])
    assert selected == ["c2", "c1"]


def test_collect_chunk_progress_tracks_pending_completed_and_order():
    plan = [
        {"chunk_id": "c1", "name": "A"},
        {"chunk_id": "c2", "name": "B"},
        {"chunk_id": "c3", "name": "C"},
    ]
    states = {
        "sid:c1": {"shards_queue": [], "shard_analyses": ["Summary A"]},
        "sid:c2": {"shards_queue": [{"name": "B"}], "shard_analyses": []},
    }

    def _load_state(workflow_id: str):
        return states.get(workflow_id)

    progress = collect_chunk_progress(
        session_id="sid",
        chunk_plan=plan,
        load_state=_load_state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert progress["completed_chunk_ids"] == ["c1"]
    assert progress["pending_chunk_ids"] == ["c2", "c3"]
    assert progress["ordered_summaries"] == ["Summary A"]


def test_build_child_work_items_from_master_plan():
    base_state = {"repo_url": "https://example.com/repo", "request": "Analyze"}
    plan = [
        {"chunk_id": "c1", "name": "Shard A", "targets": ["a.rs"], "description": "A"},
        {"chunk_id": "c2", "name": "Shard B", "targets": ["b.rs"], "description": "B"},
    ]

    work_items = build_child_work_items(
        session_id="sid-1",
        chunk_plan=plan,
        base_state=base_state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )

    assert len(work_items) == 2
    child1_id, child1_state = work_items[0]
    child2_id, child2_state = work_items[1]

    assert child1_id == "sid-1:c1"
    assert child2_id == "sid-1:c2"
    assert child1_state["chunk_id"] == "c1"
    assert child2_state["chunk_id"] == "c2"
    assert child1_state["parent_session_id"] == "sid-1"
    assert child2_state["parent_session_id"] == "sid-1"
    assert child1_state["shards_queue"] == [
        {"name": "Shard A", "targets": ["a.rs"], "description": "A"}
    ]
    assert child2_state["shards_queue"] == [
        {"name": "Shard B", "targets": ["b.rs"], "description": "B"}
    ]


def test_extract_state_or_scalar_result_prefers_state_then_dict_result_then_scalar():
    state, scalar = extract_state_or_scalar_result({"state": {"ok": True}, "result": "x"})
    assert state == {"ok": True}
    assert scalar is None

    state2, scalar2 = extract_state_or_scalar_result({"result": {"ok": True}})
    assert state2 == {"ok": True}
    assert scalar2 is None

    state3, scalar3 = extract_state_or_scalar_result({"result": 42})
    assert state3 is None
    assert scalar3 == "42"


def test_build_summary_payload_from_state():
    payload = build_summary_payload_from_state(
        {
            "harvest_dir": "/tmp/h",
            "messages": [{"content": "Done"}],
            "shard_analyses": ["A", "B"],
        },
        workflow_type="wf",
        session_id="sid-1",
    )
    assert payload == {
        "success": True,
        "session_id": "sid-1",
        "harvest_dir": "/tmp/h",
        "summary": "Done",
        "shard_summaries": ["A", "B"],
        "shards_analyzed": 2,
        "workflow_type": "wf",
    }


def test_build_summary_payload_from_chunked_result_scalar_fallback_and_error_passthrough():
    scalar_payload = build_summary_payload_from_chunked_result(
        {"success": True, "result": "complete"},
        workflow_type="wf",
    )
    assert scalar_payload["summary"] == "complete"
    assert scalar_payload["shards_analyzed"] == 0
    assert scalar_payload["workflow_type"] == "wf"

    err = {"success": False, "error": "boom", "workflow_type": "wf"}
    assert build_summary_payload_from_chunked_result(err, workflow_type="wf") == err


def test_build_summary_payload_from_chunked_step_result_state_error_guard():
    payload = build_summary_payload_from_chunked_step_result(
        {"success": True, "state": {"error": "boom"}},
        workflow_type="wf",
        session_id="sid-1",
        state_error_key="error",
    )
    assert payload == {
        "success": False,
        "error": "boom",
        "workflow_type": "wf",
    }


def test_build_summary_payload_from_chunked_step_result_success_and_scalar_fallback():
    payload = build_summary_payload_from_chunked_step_result(
        {
            "success": True,
            "state": {
                "harvest_dir": "/tmp/h",
                "messages": [{"content": "Done"}],
                "shard_analyses": ["A"],
            },
        },
        workflow_type="wf",
        session_id="sid-1",
    )
    assert payload == {
        "success": True,
        "session_id": "sid-1",
        "harvest_dir": "/tmp/h",
        "summary": "Done",
        "shard_summaries": ["A"],
        "shards_analyzed": 1,
        "workflow_type": "wf",
    }

    scalar = build_summary_payload_from_chunked_step_result(
        {"success": True, "result": "complete"},
        workflow_type="wf",
        session_id="sid-1",
    )
    assert scalar["summary"] == "complete"
    assert scalar["workflow_type"] == "wf"
    assert scalar["session_id"] == "sid-1"


@pytest.mark.asyncio
async def test_run_chunked_action_dispatch_guards_missing_session_and_state_and_unknown_action():
    def _load_state(session_id: str):
        return {"queue": []} if session_id == "sid-1" else None

    missing_session = await run_chunked_action_dispatch(
        action="shard",
        session_id="",
        workflow_type="wf",
        load_state=_load_state,
        on_shard=lambda _sid, _state: {"success": True},
    )
    assert missing_session.get("success") is False
    assert "session_id" in missing_session.get("error", "")

    missing_state = await run_chunked_action_dispatch(
        action="synthesize",
        session_id="missing",
        workflow_type="wf",
        load_state=_load_state,
        on_synthesize=lambda _sid, _state: {"success": True},
    )
    assert missing_state.get("success") is False
    assert "No state found" in missing_state.get("error", "")

    unknown = await run_chunked_action_dispatch(
        action="unknown",
        session_id="sid-1",
        workflow_type="wf",
        load_state=_load_state,
    )
    assert unknown.get("success") is False
    assert "Unknown action" in unknown.get("error", "")


@pytest.mark.asyncio
async def test_run_chunked_action_dispatch_routes_start_and_chunk_alias_to_handlers():
    async def _on_start() -> dict[str, str | bool]:
        return {"success": True, "route": "start"}

    async def _on_shard(session_id: str, loaded: dict[str, str]) -> dict[str, str | bool]:
        return {"success": True, "route": "shard", "sid": session_id, "v": loaded["v"]}

    result_start = await run_chunked_action_dispatch(
        action="start",
        session_id="",
        workflow_type="wf",
        load_state=lambda _sid: None,
        on_start=_on_start,
    )
    assert result_start == {"success": True, "route": "start"}

    result_chunk_alias = await run_chunked_action_dispatch(
        action="chunk",
        session_id="sid-1",
        workflow_type="wf",
        load_state=lambda _sid: {"v": "ok"},
        on_shard=_on_shard,
    )
    assert result_chunk_alias == {
        "success": True,
        "route": "shard",
        "sid": "sid-1",
        "v": "ok",
    }


@pytest.mark.asyncio
async def test_run_chunked_action_dispatch_supports_custom_aliases_and_missing_state_template():
    async def _on_start() -> dict[str, str | bool]:
        return {"success": True, "route": "start"}

    async def _on_shard(session_id: str, loaded: dict[str, str]) -> dict[str, str | bool]:
        return {"success": True, "route": "shard", "sid": session_id, "v": loaded["v"]}

    result_fetch_alias = await run_chunked_action_dispatch(
        action="fetch",
        session_id="",
        workflow_type="wf",
        load_state=lambda _sid: None,
        on_start=_on_start,
        action_aliases={"fetch": "start"},
    )
    assert result_fetch_alias == {"success": True, "route": "start"}

    result_batch_alias = await run_chunked_action_dispatch(
        action="batch",
        session_id="sid-1",
        workflow_type="wf",
        load_state=lambda _sid: {"v": "ok"},
        on_shard=_on_shard,
        action_aliases={"batch": "shard"},
    )
    assert result_batch_alias == {
        "success": True,
        "route": "shard",
        "sid": "sid-1",
        "v": "ok",
    }

    missing_state = await run_chunked_action_dispatch(
        action="batch",
        session_id="sid-missing",
        workflow_type="wf",
        load_state=lambda _sid: None,
        on_shard=_on_shard,
        action_aliases={"batch": "shard"},
        session_missing_error="session_id not found: {session_id}",
    )
    assert missing_state == {
        "success": False,
        "error": "session_id not found: sid-missing",
        "workflow_type": "wf",
    }


@pytest.mark.asyncio
async def test_run_chunked_lazy_start_batch_dispatch_routes_start_and_batch():
    session = object()
    session_store: dict[str, tuple[object, dict[str, Any]]] = {
        "sid-1": (
            session,
            {
                "batch_size": 2,
                "max_chunks": 4,
                "cached_results_ready": False,
                "cached_results": [],
            },
        )
    }

    async def _on_start() -> dict[str, str | bool]:
        return {"success": True, "route": "start"}

    async def _fetch_rows(_state: dict[str, Any]) -> list[str]:
        return ["a", "b", "c", "d"]

    def _load_state(session_id: str) -> dict[str, Any] | None:
        if session_id == "sid-1":
            return {"query": "x"}
        return None

    def _load_session_state(session_id: str) -> tuple[object, dict[str, Any]] | None:
        return session_store.get(session_id)

    def _save_session_state(saved_session: object, state: dict[str, Any]) -> None:
        session_store["sid-1"] = (saved_session, state)

    start = await run_chunked_lazy_start_batch_dispatch(
        action="start",
        session_id="",
        batch_index=0,
        workflow_type="wf",
        load_state=_load_state,
        on_start=_on_start,
        load_session_state=_load_session_state,
        save_session_state=_save_session_state,
        fetch_rows=_fetch_rows,
    )
    assert start == {"success": True, "route": "start"}

    batch = await run_chunked_lazy_start_batch_dispatch(
        action="batch",
        session_id="sid-1",
        batch_index=1,
        workflow_type="wf",
        load_state=_load_state,
        on_start=_on_start,
        load_session_state=_load_session_state,
        save_session_state=_save_session_state,
        fetch_rows=_fetch_rows,
    )
    assert batch["status"] == "success"
    assert batch["batch"] == ["c", "d"]


@pytest.mark.asyncio
async def test_run_chunked_lazy_start_batch_dispatch_error_paths():
    async def _on_start() -> dict[str, str | bool]:
        return {"success": True, "route": "start"}

    def _load_state(_session_id: str) -> dict[str, Any] | None:
        return None

    missing_session = await run_chunked_lazy_start_batch_dispatch(
        action="batch",
        session_id="",
        batch_index=0,
        workflow_type="wf",
        load_state=_load_state,
        on_start=_on_start,
        load_session_state=lambda _sid: None,
        save_session_state=lambda _session, _state: None,
        fetch_rows=lambda _state: asyncio.sleep(0),  # not used
    )
    assert missing_session.get("success") is False
    assert "session_id required" in missing_session.get("error", "")

    missing_state = await run_chunked_lazy_start_batch_dispatch(
        action="batch",
        session_id="sid-missing",
        batch_index=0,
        workflow_type="wf",
        load_state=_load_state,
        on_start=_on_start,
        load_session_state=lambda _sid: None,
        save_session_state=lambda _session, _state: None,
        fetch_rows=lambda _state: asyncio.sleep(0),  # not used
        session_missing_error="session_id not found: {session_id}",
    )
    assert missing_state == {
        "success": False,
        "error": "session_id not found: sid-missing",
        "workflow_type": "wf",
    }


@pytest.mark.asyncio
async def test_run_chunked_auto_complete_runs_full_workflow():
    """Core: run_chunked_auto_complete runs start -> step x N -> synthesize in one call."""

    def run_start():
        return {"queue": [{"name": "A"}, {"name": "B"}], "accumulated": []}

    def run_step(state):
        q = state.get("queue", [])
        if not q:
            return {**state, "error": "empty queue"}
        current = q[0]
        return {
            **state,
            "queue": q[1:],
            "accumulated": [*state.get("accumulated", []), current],
            "current_chunk": current,
        }

    def run_synthesize(state):
        return {**state, "final_report": {"items": state.get("accumulated", [])}}

    result = await run_chunked_auto_complete(
        "test_chunked",
        run_start,
        run_step,
        run_synthesize,
        queue_key="queue",
    )
    assert result.get("success") is True
    assert result.get("workflow_type") == "test_chunked"
    assert result.get("result", {}).get("items") == [{"name": "A"}, {"name": "B"}]
    assert isinstance(result.get("state"), dict)
    assert result.get("state", {}).get("accumulated") == [{"name": "A"}, {"name": "B"}]


@pytest.mark.asyncio
async def test_run_chunked_step_action_start_auto_completes_by_default():
    """Core: run_chunked_step with action=start and auto_complete=True runs full workflow."""

    def run_start():
        return {"queue": [{"name": "X"}], "accumulated": []}

    def run_step(state):
        q = state.get("queue", [])
        if not q:
            return {**state, "error": "empty"}
        return {
            **state,
            "queue": q[1:],
            "accumulated": [*state.get("accumulated", []), q[0]],
            "current_chunk": q[0],
        }

    def run_synthesize(state):
        return {**state, "final_report": {"done": True}}

    result = await run_chunked_step(
        "test_step",
        session_id="",
        action="start",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
        auto_complete=True,
    )
    assert result.get("success") is True
    assert result.get("result", {}).get("done") is True
    assert isinstance(result.get("state"), dict)
    assert result.get("state", {}).get("final_report", {}).get("done") is True
    assert "session_id" not in result  # Auto-complete returns final result, not session


@pytest.mark.asyncio
async def test_chunked_workflow_engine_persists_state(monkeypatch):
    """Engine should persist state across start -> shard -> synthesize."""
    import omni.langgraph.chunked.engine as engine_module

    class _FakeStore:
        _db: ClassVar[dict[tuple[str, str], dict]] = {}

        def __init__(self, workflow_type: str):
            self.workflow_type = workflow_type

        def save(self, workflow_id: str, state: dict, *, metadata=None) -> None:
            self._db[(self.workflow_type, workflow_id)] = dict(state)

        def load(self, workflow_id: str):
            return self._db.get((self.workflow_type, workflow_id))

    monkeypatch.setattr(engine_module, "WorkflowStateStore", _FakeStore)

    def run_start():
        return {"queue": [{"name": "A"}], "accumulated": []}

    def run_step(state):
        q = state.get("queue", [])
        if not q:
            return {**state, "error": "empty"}
        return {
            **state,
            "queue": q[1:],
            "accumulated": [*state.get("accumulated", []), q[0]],
            "current_chunk": q[0],
        }

    def run_synthesize(state):
        return {**state, "final_report": {"count": len(state.get("accumulated", []))}}

    engine = ChunkedWorkflowEngine(
        workflow_type="test_engine",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
    )

    started = await engine.run_step(session_id="", action="start", auto_complete=False)
    assert started.get("success") is True
    assert started.get("shard_count") == 1
    session_id = started.get("session_id")
    assert session_id

    stepped = await engine.run_step(session_id=session_id, action="shard", auto_complete=False)
    assert stepped.get("success") is True
    assert stepped.get("chunks_remaining") == 0

    finished = await engine.run_step(
        session_id=session_id,
        action="synthesize",
        auto_complete=False,
    )
    assert finished.get("success") is True
    assert finished.get("result", {}).get("count") == 1


@pytest.mark.asyncio
async def test_run_chunked_step_reports_missing_session():
    """run_chunked_step should return clear error for unknown session."""

    def run_start():
        return {"queue": [{"name": "A"}], "accumulated": []}

    def run_step(state):
        return state

    def run_synthesize(state):
        return state

    result = await run_chunked_step(
        workflow_type="test_missing_session",
        session_id="unknown-session",
        action="shard",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        auto_complete=False,
    )
    assert result.get("success") is False
    assert "session_id" in result.get("error", "")


@pytest.mark.asyncio
async def test_chunked_workflow_engine_complete_from_session(monkeypatch):
    """Engine should resume from persisted session and complete remaining steps."""
    import omni.langgraph.chunked.engine as engine_module

    class _FakeStore:
        _db: ClassVar[dict[tuple[str, str], dict]] = {}

        def __init__(self, workflow_type: str):
            self.workflow_type = workflow_type

        def save(self, workflow_id: str, state: dict, *, metadata=None) -> None:
            self._db[(self.workflow_type, workflow_id)] = dict(state)

        def load(self, workflow_id: str):
            return self._db.get((self.workflow_type, workflow_id))

    monkeypatch.setattr(engine_module, "WorkflowStateStore", _FakeStore)

    def run_start():
        return {"queue": [{"name": "A"}, {"name": "B"}], "accumulated": []}

    def run_step(state):
        q = state.get("queue", [])
        if not q:
            return state
        return {
            **state,
            "queue": q[1:],
            "accumulated": [*state.get("accumulated", []), q[0]],
            "current_chunk": q[0],
        }

    def run_synthesize(state):
        return {**state, "final_report": {"count": len(state.get("accumulated", []))}}

    engine = ChunkedWorkflowEngine(
        workflow_type="test_resume",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
    )

    start_result = await engine.run_step(session_id="", action="start", auto_complete=False)
    session_id = start_result["session_id"]

    completed = await engine.run_complete_from_session(session_id)
    assert completed.get("success") is True
    assert completed.get("session_id") == session_id
    assert completed.get("result", {}).get("count") == 2
    persisted = engine._store.load(session_id)
    assert isinstance(persisted, dict)
    assert persisted.get("final_report", {}).get("count") == 2


@pytest.mark.asyncio
async def test_run_chunked_complete_from_session_wrapper(monkeypatch):
    """Runner wrapper should resume existing session and complete workflow."""
    import omni.langgraph.chunked.engine as engine_module

    class _FakeStore:
        _db: ClassVar[dict[tuple[str, str], dict]] = {}

        def __init__(self, workflow_type: str):
            self.workflow_type = workflow_type

        def save(self, workflow_id: str, state: dict, *, metadata=None) -> None:
            del metadata
            self._db[(self.workflow_type, workflow_id)] = dict(state)

        def load(self, workflow_id: str):
            return self._db.get((self.workflow_type, workflow_id))

    monkeypatch.setattr(engine_module, "WorkflowStateStore", _FakeStore)
    store = _FakeStore("test_wrapper_resume")

    def run_start():
        return {"queue": [{"name": "A"}, {"name": "B"}], "accumulated": []}

    def run_step(state):
        q = state.get("queue", [])
        if not q:
            return state
        return {
            **state,
            "queue": q[1:],
            "accumulated": [*state.get("accumulated", []), q[0]],
            "current_chunk": q[0],
        }

    def run_synthesize(state):
        return {**state, "final_report": {"count": len(state.get("accumulated", []))}}

    start_engine = ChunkedWorkflowEngine(
        workflow_type="test_wrapper_resume",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
        store=store,
    )
    started = await start_engine.run_step(session_id="", action="start", auto_complete=False)
    session_id = started["session_id"]

    resumed = await run_chunked_complete_from_session(
        workflow_type="test_wrapper_resume",
        session_id=session_id,
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
        store=store,
    )
    assert resumed.get("success") is True
    assert resumed.get("session_id") == session_id
    assert resumed.get("result", {}).get("count") == 2


@pytest.mark.asyncio
async def test_chunked_workflow_engine_complete_from_session_missing_session():
    """Resuming with unknown session_id should return clear error."""

    def run_start():
        return {"queue": [{"name": "A"}], "accumulated": []}

    def run_step(state):
        return state

    def run_synthesize(state):
        return state

    engine = ChunkedWorkflowEngine(
        workflow_type="test_resume_missing",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
    )
    result = await engine.run_complete_from_session("missing")
    assert result.get("success") is False
    assert "session_id" in result.get("error", "")


@pytest.mark.asyncio
async def test_chunked_workflow_engine_start_hooks_customize_state_and_response():
    """Start hooks should customize persisted state and returned payload."""
    store_db: dict[str, dict] = {}
    hook_events: list[str] = []

    class _Store:
        def save(self, workflow_id: str, state: dict, *, metadata=None) -> None:
            del metadata
            store_db[workflow_id] = dict(state)

        def load(self, workflow_id: str):
            return store_db.get(workflow_id)

    def run_start():
        return {"queue": [{"name": "A"}], "foo": 1}

    def run_step(state):
        return state

    def run_synthesize(state):
        return state

    def prepare_start_state(state: dict, session_id: str) -> dict:
        return {**state, "prepared": session_id}

    def after_start_save(session_id: str, _state: dict) -> None:
        hook_events.append(f"after:{session_id}")

    def build_start_response(session_id: str, state: dict) -> dict:
        return {
            "message": "custom-start",
            "prepared": state.get("prepared"),
            "session_echo": session_id,
        }

    engine = ChunkedWorkflowEngine(
        workflow_type="test_start_hooks",
        run_start=run_start,
        run_step=run_step,
        run_synthesize=run_synthesize,
        queue_key="queue",
        store=_Store(),
        prepare_start_state=prepare_start_state,
        after_start_save=after_start_save,
        build_start_response=build_start_response,
        session_id_factory=lambda: "sid-hook",
    )

    result = await engine.run_step(session_id="", action="start", auto_complete=False)
    assert result.get("success") is True
    assert result.get("session_id") == "sid-hook"
    assert result.get("workflow_type") == "test_start_hooks"
    assert result.get("message") == "custom-start"
    assert result.get("prepared") == "sid-hook"
    assert result.get("session_echo") == "sid-hook"
    assert store_db["sid-hook"].get("prepared") == "sid-hook"
    assert hook_events == ["after:sid-hook"]


@pytest.mark.asyncio
async def test_run_chunked_parallel_selected_preserves_input_order():
    """Parallel selected helper should return results in selected_ids order."""

    async def process_selected(item_id: str) -> dict[str, str]:
        if item_id == "c1":
            await asyncio.sleep(0.01)
        return {"chunk_id": item_id}

    results = await run_chunked_parallel_selected(
        ["c1", "c2", "c3"],
        process_selected,
    )
    assert [item["chunk_id"] for item in results] == ["c1", "c2", "c3"]


@pytest.mark.asyncio
async def test_run_chunked_fanout_shard_validates_unknown_chunk_ids():
    """Fan-out shard helper should fail fast for unknown selected chunk ids."""
    result = await run_chunked_fanout_shard(
        workflow_type="wf",
        session_id="sid-1",
        chunk_plan=[{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        requested_chunk_ids=["c3"],
        process_selected=lambda _chunk_id: asyncio.sleep(0, result={"success": True}),
        load_state=lambda _workflow_id: {},
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result == {
        "success": False,
        "error": "Unknown chunk_id(s): c3",
        "workflow_type": "wf",
    }


@pytest.mark.asyncio
async def test_run_chunked_child_step_processes_one_child_and_persists():
    """Child-step helper should process one queued child and persist updated state."""
    states = {
        "sid-1:c1": {
            "shards_queue": [{"name": "Shard A"}],
            "current_shard": None,
            "shard_analyses": [],
        }
    }

    def _load_state(workflow_id: str):
        return states.get(workflow_id)

    def _save_state(workflow_id: str, state: dict[str, str | list[dict[str, str]]]):
        states[workflow_id] = state

    async def _run_step(state: dict[str, Any]) -> dict[str, Any]:
        return {
            **state,
            "shards_queue": [],
            "current_shard": {"name": "Shard A"},
            "shard_analyses": ["Summary A"],
        }

    result = await run_chunked_child_step(
        session_id="sid-1",
        chunk_id="c1",
        load_state=_load_state,
        save_state=_save_state,
        run_step=_run_step,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result == {
        "success": True,
        "chunk_id": "c1",
        "chunk_processed": "Shard A",
        "status": "processed",
    }
    assert states["sid-1:c1"]["shards_queue"] == []


@pytest.mark.asyncio
async def test_run_chunked_child_step_reports_missing_state():
    """Child-step helper should return a clear error when child state does not exist."""
    result = await run_chunked_child_step(
        session_id="sid-1",
        chunk_id="c404",
        load_state=lambda _workflow_id: None,
        save_state=lambda _workflow_id, _state: None,
        run_step=lambda state: state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result.get("success") is False
    assert result.get("status") == "missing"
    assert "No chunk state found for c404" in result.get("error", "")


@pytest.mark.asyncio
async def test_run_chunked_fanout_shard_runs_pending_and_reports_progress():
    """Fan-out shard helper should run pending chunks and return normalized progress."""
    states = {
        "sid-1:c1": {"shards_queue": [{"name": "Shard A"}], "shard_analyses": []},
        "sid-1:c2": {"shards_queue": [{"name": "Shard B"}], "shard_analyses": []},
    }

    def _load_state(workflow_id: str):
        return states.get(workflow_id)

    async def _process_selected(chunk_id: str) -> dict[str, str | bool]:
        states[f"sid-1:{chunk_id}"] = {
            "shards_queue": [],
            "shard_analyses": [f"{chunk_id}-summary"],
        }
        await asyncio.sleep(0)
        return {"success": True, "chunk_id": chunk_id}

    result = await run_chunked_fanout_shard(
        workflow_type="wf",
        session_id="sid-1",
        chunk_plan=[{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        requested_chunk_ids=[],
        process_selected=_process_selected,
        load_state=_load_state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result.get("success") is True
    assert result.get("chunks_requested") == 2
    assert result.get("chunks_remaining") == 0
    assert result.get("pending_chunk_ids") == []
    assert result.get("completed_chunk_ids") == ["c1", "c2"]
    assert result.get("next_action") == "Call action=synthesize with this session_id"


@pytest.mark.asyncio
async def test_run_chunked_fanout_synthesize_blocks_when_pending_chunks_exist():
    """Fan-out synthesize helper should fail when pending chunk ids remain."""
    states = {
        "sid-1:c1": {"shards_queue": [], "shard_analyses": ["Summary A"]},
        "sid-1:c2": {"shards_queue": [{"name": "Shard B"}], "shard_analyses": []},
    }

    def _load_state(workflow_id: str):
        return states.get(workflow_id)

    result = await run_chunked_fanout_synthesize(
        workflow_type="wf",
        session_id="sid-1",
        loaded_state={"harvest_dir": "/tmp/h"},
        chunk_plan=[{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        run_synthesize=lambda state: state,
        load_state=_load_state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result.get("success") is False
    assert result.get("session_id") == "sid-1"
    assert result.get("pending_chunk_ids") == ["c2"]
    assert "pending_chunk_ids" in result.get("error", "")


@pytest.mark.asyncio
async def test_run_chunked_fanout_synthesize_returns_summary_payload():
    """Fan-out synthesize helper should run synthesize and return normalized summary payload."""
    states = {
        "sid-1:c1": {"shards_queue": [], "shard_analyses": ["Summary A"]},
        "sid-1:c2": {"shards_queue": [], "shard_analyses": ["Summary B"]},
    }

    def _load_state(workflow_id: str):
        return states.get(workflow_id)

    async def _run_synthesize(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "harvest_dir": state.get("harvest_dir", ""),
            "messages": [{"content": "Done"}],
            "shard_analyses": state.get("shard_analyses", []),
        }

    result = await run_chunked_fanout_synthesize(
        workflow_type="wf",
        session_id="sid-1",
        loaded_state={"harvest_dir": "/tmp/h"},
        chunk_plan=[{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        run_synthesize=_run_synthesize,
        load_state=_load_state,
        build_child_id=lambda sid, cid: f"{sid}:{cid}",
    )
    assert result == {
        "success": True,
        "session_id": "sid-1",
        "harvest_dir": "/tmp/h",
        "summary": "Done",
        "shard_summaries": ["Summary A", "Summary B"],
        "shards_analyzed": 2,
        "workflow_type": "wf",
    }


@pytest.mark.asyncio
async def test_run_chunked_parallel_selected_respects_max_concurrent():
    """Parallel selected helper should honor max_concurrent limit."""
    concurrent_count = 0
    peak_concurrent = 0
    lock = asyncio.Lock()

    async def process_selected(item_id: str) -> dict[str, str]:
        nonlocal concurrent_count, peak_concurrent
        async with lock:
            concurrent_count += 1
            peak_concurrent = max(peak_concurrent, concurrent_count)
        await asyncio.sleep(0.02)
        async with lock:
            concurrent_count -= 1
        return {"chunk_id": item_id}

    results = await run_chunked_parallel_selected(
        [f"c{i}" for i in range(12)],
        process_selected,
        max_concurrent=3,
    )
    assert len(results) == 12
    assert peak_concurrent <= 3, f"Peak concurrent {peak_concurrent} exceeded limit 3"
