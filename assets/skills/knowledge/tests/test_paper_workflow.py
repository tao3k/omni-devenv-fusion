"""Tests for chunked recall workflow behavior."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from paper_workflow import _node_fetch, _node_preview, _parse_recall_output, run_chunked_recall


@pytest.mark.asyncio
async def test_node_preview_uses_single_call_recall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preview node must call recall in single-call mode to avoid recursion."""
    captured: dict[str, object] = {}

    async def _fake_recall(**kwargs):
        captured.update(kwargs)
        return json.dumps({"status": "success", "results": [{"source": "doc.md"}]})

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)

    state = {
        "query": "x",
        "preview_limit": 3,
        "collection": "knowledge_chunks",
        "error": None,
    }
    out = await _node_preview(state)

    assert out["preview_results"] == [{"source": "doc.md"}]
    assert captured["query"] == "x"
    assert captured["chunked"] is False
    assert captured["preview"] is True


@pytest.mark.asyncio
async def test_node_fetch_uses_single_call_recall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch node must call recall in single-call mode to avoid recursive workflow."""
    captured: dict[str, object] = {}
    rows = [{"chunk_index": 0}, {"chunk_index": 1}, {"chunk_index": 2}]

    async def _fake_recall(**kwargs):
        captured.update(kwargs)
        return json.dumps({"status": "success", "results": rows})

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)

    state = {
        "query": "x",
        "max_chunks": 3,
        "batch_size": 2,
        "collection": "knowledge_chunks",
        "error": None,
    }
    out = await _node_fetch(state)

    assert out["all_chunks"] == rows
    assert out["batches"] == [rows[:2], rows[2:]]
    assert captured["query"] == "x"
    assert captured["chunked"] is False
    assert captured["preview"] is False


@pytest.mark.asyncio
async def test_node_fetch_propagates_recall_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch node should propagate single-call recall errors to workflow state."""

    async def _fake_recall(**_kwargs):
        return json.dumps({"status": "error", "error": "embedding unavailable", "results": []})

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)

    state = {
        "query": "x",
        "max_chunks": 3,
        "batch_size": 2,
        "collection": "knowledge_chunks",
        "error": None,
    }
    out = await _node_fetch(state)

    assert out["error"] == "embedding unavailable"
    assert out["all_chunks"] == []
    assert out["batches"] == []


@pytest.mark.asyncio
async def test_node_fetch_suspends_monitor_for_internal_recall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Internal recall in chunked workflow should run with monitor temporarily suspended."""
    rows = [{"chunk_index": 0}]
    trace: list[str] = []

    async def _fake_recall(**_kwargs):
        trace.append("recall")
        return json.dumps({"status": "success", "results": rows})

    @contextmanager
    def _fake_suspend():
        trace.append("enter")
        try:
            yield
        finally:
            trace.append("exit")

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)
    monkeypatch.setattr("paper_workflow._suspend_skills_monitor", _fake_suspend)

    state = {
        "query": "x",
        "max_chunks": 1,
        "batch_size": 1,
        "collection": "knowledge_chunks",
        "error": None,
    }
    out = await _node_fetch(state)

    assert out["all_chunks"] == rows
    assert trace == ["enter", "recall", "exit"]


@pytest.mark.asyncio
async def test_run_chunked_recall_uses_shared_chunked_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-shot chunked recall should keep output shape with one-pass fetch."""
    calls: list[dict[str, object]] = []

    async def _fake_recall(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "status": "success",
                "results": [{"chunk_index": 0}, {"chunk_index": 1}, {"chunk_index": 2}],
            }
        )

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)

    out = await run_chunked_recall(
        query="x",
        preview_limit=1,
        batch_size=2,
        max_chunks=3,
    )

    assert out["status"] == "success"
    assert out["query"] == "x"
    assert out["preview_results"] == [{"chunk_index": 0, "preview": True}]
    assert out["all_chunks_count"] == 3
    assert out["batches"] == [[{"chunk_index": 0}, {"chunk_index": 1}], [{"chunk_index": 2}]]
    assert len(out["results"]) == 3
    assert len(calls) == 1
    assert all(call.get("chunked") is False for call in calls)
    assert all(call.get("preview") is False for call in calls)


@pytest.mark.asyncio
async def test_run_chunked_recall_returns_error_when_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chunked one-shot result should be error when internal fetch fails."""

    async def _fake_recall(**_kwargs):
        return json.dumps({"status": "error", "error": "embedding unavailable", "results": []})

    monkeypatch.setattr("paper_workflow._get_recall", lambda: _fake_recall)

    out = await run_chunked_recall(
        query="x",
        preview_limit=1,
        batch_size=2,
        max_chunks=3,
    )

    assert out["status"] == "error"
    assert out["error"] == "embedding unavailable"
    assert out["results"] == []


@pytest.mark.asyncio
async def test_run_chunked_recall_returns_error_when_engine_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine-level failure should return normalized chunked error payload."""

    async def _fake_auto_complete(*_args, **_kwargs):
        return {"success": False, "error": "chunked workflow failed"}

    monkeypatch.setattr("paper_workflow.run_chunked_auto_complete", _fake_auto_complete)

    out = await run_chunked_recall(query="x")

    assert out["query"] == "x"
    assert out["status"] == "error"
    assert out["error"] == "chunked workflow failed"
    assert out["preview_results"] == []
    assert out["batches"] == []
    assert out["all_chunks_count"] == 0
    assert out["results"] == []


@pytest.mark.asyncio
async def test_run_chunked_recall_returns_error_for_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid engine payload should return normalized chunked error payload."""

    async def _fake_auto_complete(*_args, **_kwargs):
        return {"success": True, "result": {"status": "success"}}

    monkeypatch.setattr("paper_workflow.run_chunked_auto_complete", _fake_auto_complete)

    out = await run_chunked_recall(query="x")

    assert out["query"] == "x"
    assert out["status"] == "error"
    assert out["error"] == "Invalid chunked workflow payload"
    assert out["preview_results"] == []
    assert out["batches"] == []
    assert out["all_chunks_count"] == 0
    assert out["results"] == []


def test_parse_recall_output_supports_mcp_canonical_dict() -> None:
    """Parser should unwrap MCP canonical dict payload."""
    raw = {
        "content": [
            {
                "type": "text",
                "text": '{"status":"success","results":[{"source":"doc.md"}]}',
            }
        ],
        "isError": False,
    }
    parsed = _parse_recall_output(raw)
    assert parsed["status"] == "success"
    assert parsed["results"] == [{"source": "doc.md"}]
