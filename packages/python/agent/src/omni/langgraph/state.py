"""
omni/core/state.py - LangGraph State & Checkpoint System

Persistent State Machine for ReAct workflow with checkpoint persistence:
- GraphState: TypedDict for ReAct state (messages, context, plan, error_count)
- StateCheckpointer: RustLanceCheckpointSaver-based checkpoint (omni-vector)
- Cross-session memory recovery

Usage:
    from omni.core.state import GraphState, StateCheckpointer, get_checkpointer

    # Create checkpointer
    checkpointer = get_checkpointer()

    # Save checkpoint
    state = GraphState(
        messages=[{"role": "user", "content": "Fix bug"}],
        current_plan="Analyze error logs",
    )
    checkpointer.put("session_123", state)

    # Load checkpoint
    saved = checkpointer.get("session_123")
    if saved:
        state = saved  # Resume from checkpoint
"""

from __future__ import annotations

import time
import uuid
from dataclasses import field
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.langgraph.state")


# =============================================================================
# GraphState (ReAct State Definition)
# =============================================================================


class GraphState(TypedDict):
    """
    ReAct (Reasoning + Acting) state for agent workflow.

    Defines the complete state snapshot for checkpoint persistence.
    """

    # Chat history - auto-appended during conversation
    messages: list[dict[str, Any]]

    # Long-term memory references (Neural Matrix context IDs)
    context_ids: list[str]

    # Current plan (for multi-step tasks)
    current_plan: str

    # Error count (for Reflexion self-correction)
    error_count: int

    # Additional workflow state
    workflow_state: dict[str, Any]


# =============================================================================
# Checkpoint Models (Pydantic Shield)
# =============================================================================


class StateCheckpoint(BaseModel):
    """
    Serializable checkpoint for state persistence.

    Frozen=True for immutability.
    """

    model_config = ConfigDict(frozen=True)

    thread_id: str  # Session identifier
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    state: dict[str, Any]
    parent_checkpoint_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> StateCheckpoint:
        """Deserialize from JSON string."""
        return cls.model_validate_json(data)


class CheckpointMetadata(BaseModel):
    """Metadata about a checkpoint."""

    model_config = ConfigDict(frozen=True)

    thread_id: str
    checkpoint_id: str
    parent_checkpoint_id: str | None
    timestamp: float
    state_keys: list[str]
    state_size_bytes: int


# =============================================================================
# State Checkpointer (Rust-backed via omni-vector)
# =============================================================================


class StateCheckpointer:
    """
    Rust-backed state checkpointer using omni-vector LanceDB.

    Features:
    - Global connection pooling via Rust singleton
    - Automatic checkpoint history (parent links)
    - Configurable checkpoint intervals
    - High-performance persistence

    This replaces the previous SQLite-based implementation with
    Rust-native storage via the omni-vector crate.
    """

    def __init__(
        self,
        table_name: str = "state_checkpoints",
        checkpoint_interval: int = 1,
    ):
        """
        Initialize the checkpointer.

        Args:
            table_name: Table name for state checkpoints
            checkpoint_interval: Checkpoint every N updates (default: 1 for immediate save)
        """
        self._table_name = table_name
        self._checkpoint_interval = checkpoint_interval
        self._update_count = 0
        self._current_checkpoint_id: str | None = None

        try:
            from omni_core_rs import create_checkpoint_store
        except ImportError as e:
            raise RuntimeError(
                "Rust bindings (omni_core_rs) are required for StateCheckpointer."
            ) from e
        from omni.foundation.config.database import get_checkpoint_db_path

        db_path = str(get_checkpoint_db_path())
        self._store = create_checkpoint_store(db_path, 1536)

        logger.info(
            "state_checkpointer_initialized",
            table_name=table_name,
        )

    def put(
        self,
        thread_id: str,
        state: GraphState,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Save a checkpoint for the given thread.

        Args:
            thread_id: Thread/session identifier
            state: GraphState to persist
            metadata: Optional metadata

        Returns:
            checkpoint_id: ID of the saved checkpoint
        """
        self._update_count += 1

        checkpoint_id = str(uuid.uuid4())[:8]

        checkpoint = StateCheckpoint(
            thread_id=thread_id,
            state=dict(state),
            parent_checkpoint_id=self._current_checkpoint_id,
            metadata=metadata or {},
        )

        # Only save if interval reached or forced
        if self._update_count >= self._checkpoint_interval:
            self._save_checkpoint(checkpoint)
            self._update_count = 0

        self._current_checkpoint_id = checkpoint_id

        return checkpoint_id

    def _save_checkpoint(self, checkpoint: StateCheckpoint) -> None:
        """Save checkpoint to Rust store."""
        import json

        try:
            from omni.foundation.api.checkpoint_schema import validate_checkpoint_write

            content = checkpoint.to_json()
            metadata_json = json.dumps(checkpoint.metadata)
            payload = {
                "checkpoint_id": checkpoint.checkpoint_id,
                "thread_id": checkpoint.thread_id,
                "timestamp": checkpoint.timestamp,
                "content": content,
                "parent_id": checkpoint.parent_checkpoint_id,
                "embedding": None,
                "metadata": metadata_json,
            }
            validate_checkpoint_write(self._table_name, payload)

            self._store.save_checkpoint(
                table_name=self._table_name,
                checkpoint_id=payload["checkpoint_id"],
                thread_id=payload["thread_id"],
                content=payload["content"],
                timestamp=payload["timestamp"],
                parent_id=payload["parent_id"],
                embedding=payload["embedding"],
                metadata=payload["metadata"],
            )

            logger.debug(
                "checkpoint_saved",
                thread_id=checkpoint.thread_id,
                checkpoint_id=checkpoint.checkpoint_id,
            )
        except Exception as e:
            logger.error(
                "checkpoint_save_failed",
                thread_id=checkpoint.thread_id,
                error=str(e),
            )
            raise

    def get(self, thread_id: str) -> GraphState | None:
        """
        Get the latest state for a thread.

        Args:
            thread_id: Thread/session identifier

        Returns:
            Latest GraphState or None if not found
        """
        try:
            content = self._store.get_latest(self._table_name, thread_id)

            if not content:
                return None

            checkpoint = StateCheckpoint.from_json(content)
            self._current_checkpoint_id = checkpoint.checkpoint_id

            return GraphState(**checkpoint.state)
        except Exception as e:
            logger.error("checkpoint_get_failed", thread_id=thread_id, error=str(e))
            return None

    def get_latest_checkpoint_id(self, thread_id: str) -> str | None:
        """Get the latest checkpoint ID for a thread."""
        try:
            content = self._store.get_latest(self._table_name, thread_id)
            if content:
                checkpoint = StateCheckpoint.from_json(content)
                return checkpoint.checkpoint_id
        except Exception:
            pass
        return None

    def get_history(self, thread_id: str, limit: int = 10) -> list[CheckpointMetadata]:
        """
        Get checkpoint history for a thread.

        Args:
            thread_id: Thread/session identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata (newest first)
        """
        try:
            history_contents = self._store.get_history(self._table_name, thread_id, limit)

            history = []
            for content in history_contents:
                checkpoint = StateCheckpoint.from_json(content)
                history.append(
                    CheckpointMetadata(
                        thread_id=thread_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        parent_checkpoint_id=checkpoint.parent_checkpoint_id,
                        timestamp=checkpoint.timestamp,
                        state_keys=list(checkpoint.state.keys()),
                        state_size_bytes=len(content),
                    )
                )
            return history
        except Exception as e:
            logger.error("checkpoint_history_failed", thread_id=thread_id, error=str(e))
            return []

    def get_thread_ids(self) -> list[str]:
        """Get all thread IDs with checkpoints."""
        # Note: This would require a list_threads method in Rust store
        # For now, return empty list
        return []

    def delete_thread(self, thread_id: str) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread/session identifier

        Returns:
            Number of deleted checkpoints
        """
        try:
            count = self._store.delete_thread(self._table_name, thread_id)
            logger.info(
                "thread_deleted",
                thread_id=thread_id,
                checkpoints_deleted=count,
            )
            return count
        except Exception as e:
            logger.error("thread_delete_failed", thread_id=thread_id, error=str(e))
            return 0

    def clear(self) -> int:
        """Clear all checkpoints (use with caution)."""
        logger.warning("checkpoints_cleared_not_implemented")
        return 0


# =============================================================================
# Global Singleton
# =============================================================================


_checkpointer: StateCheckpointer | None = None
_checkpointer_lock: Any = None  # Will use None for simple singleton


def get_checkpointer() -> StateCheckpointer:
    """Get the global checkpointer instance."""
    global _checkpointer, _checkpointer_lock
    if _checkpointer_lock is None:
        _checkpointer_lock = True
    if _checkpointer is None:
        _checkpointer = StateCheckpointer()
    return _checkpointer


# =============================================================================
# State Management Utilities
# =============================================================================


def create_initial_state(
    messages: list[dict[str, Any]] | None = None,
    context_ids: list[str] | None = None,
) -> GraphState:
    """
    Create an initial GraphState for a new session.

    Args:
        messages: Optional initial messages
        context_ids: Optional context IDs for RAG

    Returns:
        Initialized GraphState
    """
    return GraphState(
        messages=messages or [],
        context_ids=context_ids or [],
        current_plan="",
        error_count=0,
        workflow_state={},
    )


def merge_state(existing: GraphState, updates: dict[str, Any]) -> GraphState:
    """
    Merge updates into existing state.

    Args:
        existing: Existing GraphState
        updates: Updates to apply

    Returns:
        New GraphState with updates applied
    """
    new_state = dict(existing)

    # Auto-append messages
    if "messages" in updates:
        if isinstance(updates["messages"], list):
            new_state["messages"] = existing["messages"] + updates["messages"]
        else:
            new_state["messages"] = existing["messages"] + [updates["messages"]]

    # Merge other fields
    for key, value in updates.items():
        if key != "messages":
            new_state[key] = value

    return GraphState(**new_state)


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "CheckpointMetadata",
    "GraphState",
    "StateCheckpoint",
    "StateCheckpointer",
    "create_initial_state",
    "get_checkpointer",
    "merge_state",
]
