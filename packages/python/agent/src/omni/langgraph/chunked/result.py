"""
Result normalization helpers for chunked workflows.

Provides reusable adapters to transform chunked engine outputs into a stable
summary payload shape used by skill tools.
"""

from __future__ import annotations

from typing import Any


def extract_state_or_scalar_result(
    result: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Extract state dict when available, otherwise scalar string fallback."""
    state = result.get("state")
    if isinstance(state, dict):
        return state, None

    payload = result.get("result")
    if isinstance(payload, dict):
        return payload, None
    if payload is None:
        return None, None
    return None, str(payload)


def build_summary_payload_from_state(
    state: dict[str, Any],
    *,
    workflow_type: str,
    session_id: str | None = None,
    harvest_key: str = "harvest_dir",
    messages_key: str = "messages",
    message_content_key: str = "content",
    summaries_key: str = "shard_analyses",
) -> dict[str, Any]:
    """Build a standardized summary payload from workflow state."""
    messages = state.get(messages_key, [])
    summary = ""
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            summary = str(first.get(message_content_key, "") or "")
        elif isinstance(first, str):
            summary = first

    summaries = state.get(summaries_key, [])
    if not isinstance(summaries, list):
        summaries = []

    payload: dict[str, Any] = {
        "success": True,
        "harvest_dir": state.get(harvest_key, ""),
        "summary": summary,
        "shard_summaries": summaries,
        "shards_analyzed": len(summaries),
        "workflow_type": workflow_type,
    }
    if session_id:
        payload["session_id"] = session_id
    return payload


def build_summary_payload_from_chunked_result(
    result: dict[str, Any],
    *,
    workflow_type: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Normalize chunked result payload into standardized summary shape.

    If state (or dict result) exists, derives summary from state.
    If only scalar result exists, maps it into summary fallback payload.
    """
    if not result.get("success"):
        return dict(result)

    state, scalar = extract_state_or_scalar_result(result)
    if isinstance(state, dict):
        return build_summary_payload_from_state(
            state,
            workflow_type=workflow_type,
            session_id=session_id,
        )

    return {
        "success": True,
        "harvest_dir": "",
        "summary": str(scalar or ""),
        "shard_summaries": [],
        "shards_analyzed": 0,
        "workflow_type": workflow_type,
        **({"session_id": session_id} if session_id else {}),
    }


def build_summary_payload_from_chunked_step_result(
    result: dict[str, Any],
    *,
    workflow_type: str,
    session_id: str | None = None,
    state_error_key: str = "error",
    include_session_in_error: bool = False,
) -> dict[str, Any]:
    """
    Normalize one chunked step result into summary payload with optional state-error guard.

    This is useful for action=synthesize style flows where result success can be true
    but the returned state may still carry a domain-level error field.
    """
    if not result.get("success"):
        return dict(result)

    state, _scalar = extract_state_or_scalar_result(result)
    if isinstance(state, dict) and state_error_key and state.get(state_error_key):
        payload: dict[str, Any] = {
            "success": False,
            "error": str(state[state_error_key]),
            "workflow_type": workflow_type,
        }
        if include_session_in_error and session_id:
            payload["session_id"] = session_id
        return payload

    return build_summary_payload_from_chunked_result(
        result,
        workflow_type=workflow_type,
        session_id=session_id,
    )


__all__ = [
    "build_summary_payload_from_chunked_result",
    "build_summary_payload_from_chunked_step_result",
    "build_summary_payload_from_state",
    "extract_state_or_scalar_result",
]
