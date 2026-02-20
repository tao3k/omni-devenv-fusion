"""context_delivery.sessions - Persistent workflow and chunked session helpers.

Common storage wrappers for multi-step skill tools:
- WorkflowStateStore: generic state persistence for action-based workflows
- ChunkedSessionStore: specialized start/batch persistence for large payloads
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from omni.foundation.checkpoint import (
    delete_workflow_state,
    load_workflow_state,
    save_workflow_state,
)

from .strategies import ChunkedSession, create_chunked_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    ActionWorkflowHandler = Callable[[str, dict[str, Any] | None], Awaitable[Any] | Any]


def _normalize_workflow_id(workflow_id: str) -> str:
    return str(workflow_id or "").strip()


def normalize_chunked_action_name(
    action: Any,
    *,
    action_aliases: Mapping[str, str] | None = None,
) -> str:
    """Normalize action name with optional alias resolution."""
    normalized = str(action or "").strip().lower()
    if not normalized:
        return ""

    alias_map: dict[str, str] = {}
    if action_aliases:
        for src, dst in action_aliases.items():
            src_norm = str(src or "").strip().lower()
            dst_norm = str(dst or "").strip().lower()
            if src_norm and dst_norm:
                alias_map[src_norm] = dst_norm

    visited: set[str] = set()
    while normalized in alias_map and normalized not in visited:
        visited.add(normalized)
        normalized = alias_map[normalized]
    return normalized


def validate_chunked_action(
    action: Any,
    *,
    allowed_actions: set[str],
    action_aliases: Mapping[str, str] | None = None,
    allow_empty: bool = True,
    error_template: str = "action must be one of: {allowed_actions}",
) -> tuple[str, dict[str, Any] | None]:
    """Return normalized action and standardized invalid-action payload."""
    normalized = normalize_chunked_action_name(action, action_aliases=action_aliases)
    allowed = {
        str(item or "").strip().lower() for item in allowed_actions if str(item or "").strip()
    }

    if not normalized and allow_empty:
        return "", None
    if normalized in allowed:
        return normalized, None

    allowed_str = ", ".join(sorted(allowed))
    message = error_template.format(
        action=normalized,
        allowed=allowed_str,
        allowed_actions=allowed_str,
    )
    return normalized, {
        "status": "error",
        "message": message,
        "action": normalized,
    }


class WorkflowStateStore:
    """Checkpoint-backed persistence wrapper for multi-step workflow state."""

    def __init__(self, workflow_type: str) -> None:
        self.workflow_type = workflow_type

    def save(
        self,
        workflow_id: str,
        state: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save workflow state to checkpoint store (Rust checkpoint backend)."""
        wid = _normalize_workflow_id(workflow_id)
        if not wid or not isinstance(state, dict):
            return
        payload = dict(state)
        ok = save_workflow_state(self.workflow_type, wid, payload, metadata=metadata)
        if not ok:
            raise RuntimeError(
                f"Failed to persist workflow state: workflow_type={self.workflow_type}, workflow_id={wid}"
            )

    def load(self, workflow_id: str) -> dict[str, Any] | None:
        """Load workflow state from checkpoint store."""
        wid = _normalize_workflow_id(workflow_id)
        if not wid:
            return None
        raw = load_workflow_state(self.workflow_type, wid)
        return raw if isinstance(raw, dict) else None

    def delete(self, workflow_id: str) -> None:
        """Delete workflow state from checkpoint store."""
        wid = _normalize_workflow_id(workflow_id)
        if not wid:
            return
        delete_workflow_state(self.workflow_type, wid)


class ActionWorkflowEngine:
    """Common action dispatcher for multi-step skill workflows.

    Skills can reuse this engine to standardize:
    - action normalization/validation
    - workflow_id requirement checks
    - persisted state loading checks
    - async/sync handler invocation
    """

    def __init__(
        self,
        *,
        workflow_type: str,
        allowed_actions: set[str],
        store: WorkflowStateStore | None = None,
        action_aliases: Mapping[str, str] | None = None,
        invalid_action_template: str = "action must be one of: {allowed_actions}",
    ) -> None:
        self.workflow_type = workflow_type
        self.allowed_actions = {
            str(item or "").strip().lower() for item in allowed_actions if str(item or "").strip()
        }
        self.store = store or WorkflowStateStore(workflow_type)
        self.action_aliases = dict(action_aliases or {})
        self.invalid_action_template = invalid_action_template

    def normalize_action(
        self,
        action: Any,
        *,
        allow_empty: bool = False,
    ) -> tuple[str, dict[str, Any] | None]:
        """Normalize/validate action with standardized error payload."""
        normalized, error = validate_chunked_action(
            action,
            allowed_actions=self.allowed_actions,
            action_aliases=self.action_aliases,
            allow_empty=allow_empty,
            error_template=self.invalid_action_template,
        )
        if error is None:
            return normalized, None
        return normalized, {
            **error,
            "workflow_type": self.workflow_type,
            "error_source": "action_workflow",
        }

    async def dispatch(
        self,
        *,
        action: Any,
        workflow_id: str,
        handlers: Mapping[str, ActionWorkflowHandler],
        require_workflow_id_for: set[str] | None = None,
        require_state_for: set[str] | None = None,
        missing_workflow_id_template: str = "workflow_id required for action={action}",
        missing_state_template: str = "workflow_id not found: {workflow_id}",
        workflow_id_field: str = "workflow_id",
        allow_empty_action: bool = False,
        load_state: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> Any:
        """Dispatch one action with shared validation and state loading checks."""
        normalized_action, action_error = self.normalize_action(
            action, allow_empty=allow_empty_action
        )
        if action_error is not None:
            return action_error

        handler = handlers.get(normalized_action)
        if handler is None:
            return {
                "status": "error",
                "action": normalized_action,
                "message": self.invalid_action_template.format(
                    action=normalized_action,
                    allowed_actions=", ".join(sorted(self.allowed_actions)),
                    allowed=", ".join(sorted(self.allowed_actions)),
                ),
                "workflow_type": self.workflow_type,
                "error_source": "action_workflow",
            }

        require_workflow_id_for = {
            str(item or "").strip().lower()
            for item in (require_workflow_id_for or set())
            if str(item or "").strip()
        }
        require_state_for = {
            str(item or "").strip().lower()
            for item in (require_state_for or set())
            if str(item or "").strip()
        }

        wid = _normalize_workflow_id(workflow_id)
        if normalized_action in require_workflow_id_for and not wid:
            return {
                "status": "error",
                "action": normalized_action,
                "message": missing_workflow_id_template.format(
                    action=normalized_action,
                    workflow_id=wid,
                    workflow_id_field=workflow_id_field,
                ),
                "workflow_type": self.workflow_type,
                "error_source": "action_workflow",
            }

        loaded_state: dict[str, Any] | None = None
        if normalized_action in require_state_for:
            if not wid:
                return {
                    "status": "error",
                    "action": normalized_action,
                    "message": missing_workflow_id_template.format(
                        action=normalized_action,
                        workflow_id=wid,
                        workflow_id_field=workflow_id_field,
                    ),
                    "workflow_type": self.workflow_type,
                    "error_source": "action_workflow",
                }
            state_loader = load_state or self.store.load
            loaded_state = state_loader(wid)
            if not isinstance(loaded_state, dict):
                return {
                    "status": "error",
                    "action": normalized_action,
                    "message": missing_state_template.format(
                        action=normalized_action,
                        workflow_id=wid,
                        workflow_id_field=workflow_id_field,
                    ),
                    "workflow_type": self.workflow_type,
                    "error_source": "action_workflow",
                }

        out = handler(wid, loaded_state)
        return await out if asyncio.iscoroutine(out) else out


def _normalize_state(raw: Any, *, session_id: str) -> tuple[ChunkedSession, dict[str, Any]] | None:
    """Convert persisted state dict into a ChunkedSession + metadata tuple."""
    if not isinstance(raw, dict):
        return None
    batches = raw.get("batches")
    if not isinstance(batches, list):
        return None
    text_batches = [b for b in batches if isinstance(b, str)]
    if not text_batches:
        text_batches = [""]
    try:
        batch_size = int(raw.get("batch_size", 28_000))
    except (TypeError, ValueError):
        batch_size = 28_000
    if batch_size <= 0:
        batch_size = 28_000
    try:
        total_chars = int(raw.get("total_chars", sum(len(b) for b in text_batches)))
    except (TypeError, ValueError):
        total_chars = sum(len(b) for b in text_batches)
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    session = ChunkedSession(
        session_id=session_id,
        batches=text_batches,
        batch_size=batch_size,
        total_chars=max(0, total_chars),
    )
    return session, metadata


class ChunkedSessionStore:
    """Persistence wrapper for chunked sessions (checkpoint-backed)."""

    def __init__(self, workflow_type: str) -> None:
        self.workflow_type = workflow_type
        self._state_store = WorkflowStateStore(workflow_type)

    def save(self, session: ChunkedSession, *, metadata: dict[str, Any] | None = None) -> None:
        """Save a chunked session to checkpoint storage."""
        state = {
            "batches": list(session.batches),
            "batch_size": int(session.batch_size),
            "total_chars": int(session.total_chars),
            "metadata": metadata or {},
        }
        self._state_store.save(session.session_id, state)

    def create(
        self,
        content: str,
        *,
        batch_size: int = 28_000,
        metadata: dict[str, Any] | None = None,
    ) -> ChunkedSession:
        """Create + persist a chunked session."""
        session = create_chunked_session(content, batch_size=batch_size)
        self.save(session, metadata=metadata)
        return session

    def create_start_payload(
        self,
        *,
        content: str,
        batch_size: int = 28_000,
        metadata: dict[str, Any] | None = None,
        action_name: str = "start",
        batch_action_name: str = "batch",
        status: str = "success",
        message_template: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create + persist session and return a standardized action=start payload."""
        session = self.create(content, batch_size=batch_size, metadata=metadata)
        max_index = max(0, session.batch_count - 1)
        message = (
            message_template
            or "Call action={batch_action} with session_id and batch_index=0..{max_index} to read all chunks."
        )
        payload: dict[str, Any] = {
            "status": status,
            "action": action_name,
            "session_id": session.session_id,
            "batch_size": session.batch_size,
            "batch_count": session.batch_count,
            "batch_index": 0,
            "batch": session.get_batch(0) or "",
            "message": message.format(batch_action=batch_action_name, max_index=max_index),
        }
        if extra:
            payload.update(extra)
        return payload

    def load(self, session_id: str) -> tuple[ChunkedSession, dict[str, Any]] | None:
        """Load a chunked session from checkpoint store."""
        sid = _normalize_workflow_id(session_id)
        if not sid:
            return None

        raw = self._state_store.load(sid)
        normalized = _normalize_state(raw, session_id=sid)
        return normalized if normalized is not None else None

    def get_batch_payload(
        self,
        *,
        session_id: str,
        batch_index: Any,
        action_name: str = "batch",
    ) -> dict[str, Any]:
        """Return a normalized action=batch payload used by skill tools."""
        sid = (session_id or "").strip()
        if not sid:
            return {
                "status": "error",
                "action": action_name,
                "message": f"session_id is required for action={action_name}",
            }

        loaded = self.load(sid)
        if loaded is None:
            return {
                "status": "error",
                "action": action_name,
                "session_id": sid,
                "message": f"session_id not found: {sid}",
            }
        session, _metadata = loaded
        try:
            idx = int(batch_index)
        except (TypeError, ValueError):
            idx = -1

        if idx < 0 or idx >= session.batch_count:
            return {
                "status": "error",
                "action": action_name,
                "session_id": sid,
                "batch_index": idx,
                "batch_count": session.batch_count,
                "message": f"batch_index must be 0..{session.batch_count - 1}",
            }

        return {
            "status": "success",
            "action": action_name,
            "session_id": sid,
            "batch_index": idx,
            "batch_count": session.batch_count,
            "batch": session.get_batch(idx) or "",
        }


__all__ = [
    "ActionWorkflowEngine",
    "ChunkedSessionStore",
    "WorkflowStateStore",
    "normalize_chunked_action_name",
    "validate_chunked_action",
]
