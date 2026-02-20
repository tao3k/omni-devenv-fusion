"""
Reusable chunked workflow engine for LangGraph-style long-running skills.

This engine standardizes action=start|shard|synthesize execution with:
- one-shot auto-complete mode for start
- persisted workflow state across calls
- consistent response payloads for skill tools
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

from omni.foundation.api.tool_context import run_with_heartbeat
from omni.foundation.config.logging import get_logger
from omni.foundation.context_delivery import WorkflowStateStore

logger = get_logger("omni.langgraph.chunked")


class WorkflowStoreLike(Protocol):
    """Minimal persistence protocol required by ChunkedWorkflowEngine."""

    def save(
        self,
        workflow_id: str,
        state: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def load(self, workflow_id: str) -> dict[str, Any] | None: ...


class ChunkedWorkflowEngine:
    """Common execution engine for chunked workflow tools."""

    def __init__(
        self,
        workflow_type: str,
        run_start: Callable[[], Any],
        run_step: Callable[[dict[str, Any]], Any],
        run_synthesize: Callable[[dict[str, Any]], Any],
        *,
        queue_key: str = "queue",
        store: WorkflowStoreLike | None = None,
        prepare_start_state: Callable[[dict[str, Any], str], Any] | None = None,
        after_start_save: Callable[[str, dict[str, Any]], Any] | None = None,
        build_start_response: Callable[[str, dict[str, Any]], Any] | None = None,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.workflow_type = workflow_type
        self._start_fn = run_start
        self._step_fn = run_step
        self._synthesize_fn = run_synthesize
        self.queue_key = queue_key
        self._store = store or WorkflowStateStore(workflow_type)
        self._prepare_start_state = prepare_start_state
        self._after_start_save = after_start_save
        self._build_start_response = build_start_response
        self._session_id_factory = session_id_factory or (lambda: uuid.uuid4().hex)

    async def run_auto_complete(self) -> dict[str, Any]:
        """Run full workflow in one call: start -> step*N -> synthesize."""

        async def _run() -> dict[str, Any]:
            state = await _maybe_await(self._start_fn())
            if state.get("error"):
                return {
                    "success": False,
                    "error": state["error"],
                    "workflow_type": self.workflow_type,
                }
            return await self._run_complete_from_state(state)

        return await run_with_heartbeat(_run())

    async def run_complete_from_session(self, session_id: str) -> dict[str, Any]:
        """Load existing session state and complete remaining step loop + synthesize."""
        sid = (session_id or "").strip()
        if not sid:
            return {
                "success": False,
                "error": "session_id required",
                "workflow_type": self.workflow_type,
            }

        loaded = self._store.load(sid)
        if not loaded:
            return {
                "success": False,
                "error": "No state found for this session_id; run action=start first.",
                "workflow_type": self.workflow_type,
            }

        async def _run() -> dict[str, Any]:
            result = await self._run_complete_from_state(loaded)
            if result.get("success"):
                state = result.get("state")
                if isinstance(state, dict):
                    self._store.save(sid, state)
                result["session_id"] = sid
            return result

        return await run_with_heartbeat(_run())

    async def run_step(
        self,
        *,
        session_id: str,
        action: str,
        auto_complete: bool = True,
    ) -> dict[str, Any]:
        """
        Execute one chunked action for this workflow.

        Supported actions: start | shard (alias chunk) | synthesize.
        """
        normalized_action = action.strip().lower()
        if normalized_action == "chunk":
            normalized_action = "shard"

        if normalized_action == "start" and auto_complete:
            return await self.run_auto_complete()

        if normalized_action == "start":
            try:
                state = await _maybe_await(self._start_fn())
            except Exception as e:
                logger.exception("Chunked start failed")
                return {
                    "success": False,
                    "error": str(e),
                    "workflow_type": self.workflow_type,
                }
            if state.get("error"):
                return {
                    "success": False,
                    "error": state["error"],
                    "workflow_type": self.workflow_type,
                }
            sid = self._session_id_factory()
            if self._prepare_start_state is not None:
                state = await _maybe_await(self._prepare_start_state(state, sid))
                if state.get("error"):
                    return {
                        "success": False,
                        "error": state["error"],
                        "workflow_type": self.workflow_type,
                    }
            self._store.save(sid, state)
            if self._after_start_save is not None:
                await _maybe_await(self._after_start_save(sid, state))
            if self._build_start_response is not None:
                start_payload = await _maybe_await(self._build_start_response(sid, state))
                if isinstance(start_payload, dict):
                    return {
                        "success": True,
                        "session_id": sid,
                        "workflow_type": self.workflow_type,
                        **start_payload,
                    }
            queue = state.get(self.queue_key, [])
            return {
                "success": True,
                "session_id": sid,
                "shard_count": len(queue),
                "workflow_type": self.workflow_type,
                "next_action": (
                    f"Call action=shard with this session_id once per chunk ({len(queue)} times), "
                    "then action=synthesize with the same session_id."
                ),
            }

        if not session_id:
            return {
                "success": False,
                "error": "session_id required for action=shard and action=synthesize",
                "workflow_type": self.workflow_type,
            }

        loaded = self._store.load(session_id)
        if not loaded:
            return {
                "success": False,
                "error": "No state found for this session_id; run action=start first.",
                "workflow_type": self.workflow_type,
            }

        if normalized_action == "shard":
            try:
                state = await _maybe_await(self._step_fn(loaded))
            except Exception as e:
                logger.exception("Chunked step failed")
                return {
                    "success": False,
                    "error": str(e),
                    "workflow_type": self.workflow_type,
                }
            if state.get("error"):
                return {
                    "success": False,
                    "error": state["error"],
                    "workflow_type": self.workflow_type,
                }
            self._store.save(session_id, state)
            queue = state.get(self.queue_key, [])
            current = state.get("current_chunk") or state.get("current_shard") or {}
            return {
                "success": True,
                "session_id": session_id,
                "chunks_remaining": len(queue),
                "chunk_processed": current.get("name", ""),
                "workflow_type": self.workflow_type,
                "next_action": (
                    "Call action=shard again with this session_id"
                    if queue
                    else "Call action=synthesize with this session_id"
                ),
            }

        if normalized_action == "synthesize":
            try:
                state = await _maybe_await(self._synthesize_fn(loaded))
            except Exception as e:
                logger.exception("Chunked synthesize failed")
                return {
                    "success": False,
                    "error": str(e),
                    "workflow_type": self.workflow_type,
                }
            return {
                "success": True,
                "session_id": session_id,
                "workflow_type": self.workflow_type,
                "result": state.get("final_report") or state.get("accumulated") or state,
                "state": state,
            }

        return {
            "success": False,
            "error": f"Unknown action: {normalized_action}. Use start | shard | synthesize.",
            "workflow_type": self.workflow_type,
        }

    async def _run_complete_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Complete queue-driven loop and synthesize from provided state."""
        current_state = state
        while current_state.get(self.queue_key):
            current_state = await _maybe_await(self._step_fn(current_state))
            if current_state.get("error"):
                return {
                    "success": False,
                    "error": current_state["error"],
                    "workflow_type": self.workflow_type,
                }
        current_state = await _maybe_await(self._synthesize_fn(current_state))
        final_result = (
            current_state.get("final_report") or current_state.get("accumulated") or current_state
        )
        return {
            "success": True,
            "workflow_type": self.workflow_type,
            "result": final_result,
            "state": current_state,
        }


async def _maybe_await(value: Any) -> Any:
    """Await coroutine values while allowing sync callables."""
    import asyncio

    if asyncio.iscoroutine(value):
        return await value
    return value


__all__ = ["ChunkedWorkflowEngine", "WorkflowStoreLike"]
