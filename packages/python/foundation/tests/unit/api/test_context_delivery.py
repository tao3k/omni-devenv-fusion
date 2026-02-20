"""Tests for omni.foundation.context_delivery - skill tool content strategies."""

import pytest

from omni.foundation.context_delivery import (
    ActionWorkflowEngine,
    ChunkedSessionStore,
    WorkflowStateStore,
    create_chunked_session,
    normalize_chunked_action_name,
    prepare_for_summary,
    validate_chunked_action,
)


def _install_fake_checkpoint_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[tuple[str, str], dict]:
    storage: dict[tuple[str, str], dict] = {}

    def _save(
        workflow_type: str,
        workflow_id: str,
        state: dict,
        parent_id=None,
        metadata=None,
    ) -> bool:
        del parent_id, metadata
        storage[(workflow_type, workflow_id)] = dict(state)
        return True

    def _load(workflow_type: str, workflow_id: str):
        state = storage.get((workflow_type, workflow_id))
        return dict(state) if isinstance(state, dict) else None

    def _delete(workflow_type: str, workflow_id: str) -> bool:
        storage.pop((workflow_type, workflow_id), None)
        return True

    monkeypatch.setattr("omni.foundation.context_delivery.sessions.save_workflow_state", _save)
    monkeypatch.setattr("omni.foundation.context_delivery.sessions.load_workflow_state", _load)
    monkeypatch.setattr("omni.foundation.context_delivery.sessions.delete_workflow_state", _delete)
    return storage


class TestPrepareForSummary:
    """Summary-only scenario (e.g. git diff)."""

    def test_short_content_unchanged(self) -> None:
        content = "short diff"
        assert prepare_for_summary(content) == content
        assert prepare_for_summary(content, max_chars=100) == content

    def test_long_content_truncated(self) -> None:
        content = "x" * 10000
        result = prepare_for_summary(content, max_chars=100)
        assert len(result) == 100 + len("\n\n_(truncated for summary)_")
        assert result.endswith("\n\n_(truncated for summary)_")

    def test_exact_boundary(self) -> None:
        content = "a" * 8000
        result = prepare_for_summary(content, max_chars=8000)
        assert result == content


class TestChunkedSession:
    """Full-content scenario (e.g. researcher repomix)."""

    def test_single_batch(self) -> None:
        content = "short"
        session = create_chunked_session(content, batch_size=100)
        assert session.batch_count == 1
        assert session.get_batch(0) == "short"
        assert session.get_batch(1) is None
        assert session.total_chars == 5

    def test_multiple_batches(self) -> None:
        content = "a" * 60000  # 60k chars
        session = create_chunked_session(content, batch_size=28000)
        assert session.batch_count == 3
        assert len(session.get_batch(0) or "") == 28000
        assert len(session.get_batch(1) or "") == 28000
        assert len(session.get_batch(2) or "") == 4000
        assert session.get_batch(3) is None
        assert session.total_chars == 60000

    def test_empty_content(self) -> None:
        session = create_chunked_session("", batch_size=1000)
        assert session.batch_count == 1
        assert session.get_batch(0) == ""
        assert session.total_chars == 0

    def test_session_id_unique(self) -> None:
        s1 = create_chunked_session("x", batch_size=1)
        s2 = create_chunked_session("x", batch_size=1)
        assert s1.session_id != s2.session_id

    def test_to_preview(self) -> None:
        content = "hello world " * 100
        session = create_chunked_session(content, batch_size=500)
        preview = session.to_preview()
        assert "session_id" in preview
        assert preview["batch_count"] >= 1
        assert preview["total_chars"] == len(content)
        assert "preview" in preview


class TestChunkedSessionStore:
    """Persistent chunked session helper for action=start/action=batch flows."""

    def test_create_and_read_batch_with_checkpoint_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = ChunkedSessionStore("test_chunked_store_memory")
        session = store.create("abcdef" * 500, batch_size=300)
        out = store.get_batch_payload(session_id=session.session_id, batch_index=0)
        assert out["status"] == "success"
        assert out["action"] == "batch"
        assert out["session_id"] == session.session_id
        assert out["batch_index"] == 0
        assert out["batch_count"] >= 1
        assert isinstance(out["batch"], str)

    def test_batch_requires_session_id(self) -> None:
        store = ChunkedSessionStore("test_chunked_store_missing_sid")
        out = store.get_batch_payload(session_id="", batch_index=0)
        assert out["status"] == "error"
        assert "session_id" in out["message"].lower()

    def test_batch_reports_not_found_for_unknown_session(self) -> None:
        store = ChunkedSessionStore("test_chunked_store_unknown_sid")
        out = store.get_batch_payload(session_id="unknown-123", batch_index=0)
        assert out["status"] == "error"
        assert "not found" in out["message"].lower()

    def test_batch_reports_index_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = ChunkedSessionStore("test_chunked_store_index")
        session = store.create("x" * 100, batch_size=50)
        out = store.get_batch_payload(session_id=session.session_id, batch_index=99)
        assert out["status"] == "error"
        assert "batch_index must be 0.." in out["message"]

    def test_create_start_payload_shapes_standard_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = ChunkedSessionStore("test_chunked_store_start_payload")
        out = store.create_start_payload(
            content="x" * 260,
            batch_size=100,
            batch_action_name="batch",
            extra={"tool": "demo"},
        )

        assert out["status"] == "success"
        assert out["action"] == "start"
        assert isinstance(out["session_id"], str)
        assert out["batch_size"] == 100
        assert out["batch_count"] == 3
        assert out["batch_index"] == 0
        assert isinstance(out["batch"], str)
        assert out["tool"] == "demo"
        assert "action=batch" in out["message"]

    def test_chunked_save_raises_when_backend_rejects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "omni.foundation.context_delivery.sessions.save_workflow_state",
            lambda *_args, **_kwargs: False,
        )
        store = ChunkedSessionStore("test_chunked_store_save_error")
        with pytest.raises(RuntimeError, match="Failed to persist workflow state"):
            store.create("x" * 64, batch_size=16)


class TestChunkedActionValidation:
    """Common action normalization/validation for chunked start/batch flows."""

    def test_normalize_action_with_aliases(self) -> None:
        normalized = normalize_chunked_action_name(
            " Fetch ",
            action_aliases={"fetch": "start", "batch": "shard"},
        )
        assert normalized == "start"

    def test_validate_action_accepts_empty_when_allowed(self) -> None:
        action_name, error = validate_chunked_action(
            "",
            allowed_actions={"start", "batch"},
            allow_empty=True,
        )
        assert action_name == ""
        assert error is None

    def test_validate_action_rejects_invalid_action(self) -> None:
        action_name, error = validate_chunked_action(
            "unknown",
            allowed_actions={"start", "batch"},
        )
        assert action_name == "unknown"
        assert isinstance(error, dict)
        assert error["status"] == "error"
        assert error["action"] == "unknown"
        assert error["message"] == "action must be one of: batch, start"


class TestWorkflowStateStore:
    """Generic workflow state helper for action-based skill tools."""

    def test_save_and_load_with_checkpoint_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = WorkflowStateStore("test_workflow_store_memory")
        state = {"status": "prepared", "files": ["a.py"]}
        store.save("wf-123", state)
        loaded = store.load("wf-123")
        assert loaded == state

    def test_load_requires_workflow_id(self) -> None:
        store = WorkflowStateStore("test_workflow_store_missing_id")
        assert store.load("") is None

    def test_save_and_load_empty_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = WorkflowStateStore("test_workflow_store_empty")
        store.save("wf-456", {})  # sanity
        loaded = store.load("wf-456")
        assert loaded == {}

    def test_save_raises_when_backend_rejects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "omni.foundation.context_delivery.sessions.save_workflow_state",
            lambda *_args, **_kwargs: False,
        )
        store = WorkflowStateStore("test_workflow_store_save_error")
        with pytest.raises(RuntimeError, match="Failed to persist workflow state"):
            store.save("wf-789", {"status": "prepared"})


class TestActionWorkflowEngine:
    """Common action workflow dispatcher for action-based skill tools."""

    @pytest.mark.asyncio
    async def test_dispatch_invalid_action_returns_standard_error(self) -> None:
        engine = ActionWorkflowEngine(
            workflow_type="test_action_engine",
            allowed_actions={"start", "approve"},
        )
        result = await engine.dispatch(
            action="unknown",
            workflow_id="",
            handlers={"start": lambda *_: {"ok": True}, "approve": lambda *_: {"ok": True}},
        )
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "action must be one of:" in result["message"]
        assert result["error_source"] == "action_workflow"

    @pytest.mark.asyncio
    async def test_dispatch_requires_workflow_id_when_configured(self) -> None:
        engine = ActionWorkflowEngine(
            workflow_type="test_action_engine_require_id",
            allowed_actions={"approve"},
        )
        result = await engine.dispatch(
            action="approve",
            workflow_id="",
            handlers={"approve": lambda *_: {"ok": True}},
            require_workflow_id_for={"approve"},
            missing_workflow_id_template="workflow_id required for action={action}",
        )
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["message"] == "workflow_id required for action=approve"

    @pytest.mark.asyncio
    async def test_dispatch_requires_state_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        engine = ActionWorkflowEngine(
            workflow_type="test_action_engine_require_state",
            allowed_actions={"status"},
        )
        result = await engine.dispatch(
            action="status",
            workflow_id="wf-missing",
            handlers={"status": lambda *_: {"ok": True}},
            require_state_for={"status"},
            missing_state_template="workflow not found: {workflow_id}",
        )
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["message"] == "workflow not found: wf-missing"

    @pytest.mark.asyncio
    async def test_dispatch_invokes_async_handler_with_loaded_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_checkpoint_backend(monkeypatch)
        store = WorkflowStateStore("test_action_engine_state_ok")
        store.save("wf-123", {"status": "prepared", "files": ["a.py"]})

        engine = ActionWorkflowEngine(
            workflow_type="test_action_engine_state_ok",
            allowed_actions={"status"},
            store=store,
        )

        async def _handler(wid: str, state: dict | None) -> dict:
            return {"workflow_id": wid, "status": state.get("status") if state else "missing"}

        result = await engine.dispatch(
            action="status",
            workflow_id="wf-123",
            handlers={"status": _handler},
            require_state_for={"status"},
        )
        assert result == {"workflow_id": "wf-123", "status": "prepared"}
