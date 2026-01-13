"""
agent/core/state.py
Phase 34: Persistent State Machine - ReAct Checkpoint System

Extends existing SessionManager with LangGraph-style checkpoint persistence:
- GraphState: TypedDict for ReAct state (messages, context, plan, error_count)
- StateCheckpointer: SQLite-based checkpoint with thread-safe access
- Cross-session memory recovery

ODF-EP v6.0 Compliance:
- Pillar A: Pydantic Shield (frozen=True)
- Pillar C: Tenacity Pattern (retry for resilience)
- Pillar D: Context-Aware Observability

Usage:
    from agent.core.state import GraphState, get_checkpointer

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

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict

from common.gitops import get_project_root

# Lazy logger - defer structlog.get_logger() to avoid import overhead
_cached_logger: Any | None = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


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

    ODF-EP v6.0: frozen=True for immutability
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
    def from_json(cls, data: str) -> "StateCheckpoint":
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
# State Checkpointer (SQLite-based)
# =============================================================================


class StateCheckpointer:
    """
    SQLite-based state checkpoint system.

    Features:
    - Thread-safe access (uses locks)
    - Automatic checkpoint history (parent links)
    - Configurable checkpoint intervals
    - Efficient JSON storage

    ODF-EP v6.0: Tenacity Pattern for resilience
    """

    _lock = threading.Lock()

    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_interval: int = 10,  # Checkpoint every N state updates
    ):
        """
        Initialize the checkpointer.

        Args:
            db_path: Path to SQLite database (auto-generated if not provided)
            checkpoint_interval: Checkpoint every N updates (default: 10)
        """
        if db_path is None:
            from common.cache_path import CACHE_DIR

            db_path = CACHE_DIR("agent", "checkpoints.db")

        self.db_path = Path(db_path)
        self.checkpoint_interval = checkpoint_interval
        self._update_count = 0
        self._current_checkpoint_id: str | None = None

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        _get_logger().bind(
            db_path=str(self.db_path),
            checkpoint_interval=checkpoint_interval,
        ).info("checkpointer_initialized")

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create checkpoints table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    timestamp REAL NOT NULL,
                    state_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
                """
            )

            # Create index for efficient thread queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_thread_id
                ON checkpoints(thread_id, timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

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
        with self._lock:
            self._update_count += 1

            # Create checkpoint
            checkpoint = StateCheckpoint(
                thread_id=thread_id,
                state=dict(state),
                parent_checkpoint_id=self._current_checkpoint_id,
                metadata=metadata or {},
            )

            # Only save if interval reached or forced
            if self._update_count >= self.checkpoint_interval:
                self._save_checkpoint(checkpoint)
                self._update_count = 0

            self._current_checkpoint_id = checkpoint.checkpoint_id

            return checkpoint.checkpoint_id

    def _save_checkpoint(self, checkpoint: StateCheckpoint) -> None:
        """Save checkpoint to SQLite."""
        import json

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate state size
            state_json_str = checkpoint.to_json()
            state_size = len(state_json_str)

            cursor.execute(
                """
                INSERT INTO checkpoints
                (thread_id, checkpoint_id, parent_checkpoint_id, timestamp, state_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.thread_id,
                    checkpoint.checkpoint_id,
                    checkpoint.parent_checkpoint_id,
                    checkpoint.timestamp,
                    state_json_str,
                    json.dumps(checkpoint.metadata),
                ),
            )

            conn.commit()
            conn.close()

            _get_logger().debug(
                "checkpoint_saved",
                thread_id=checkpoint.thread_id,
                checkpoint_id=checkpoint.checkpoint_id,
                state_size=state_size,
            )

        except Exception as e:
            _get_logger().error(
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
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT state_json, checkpoint_id, timestamp
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (thread_id,),
            )

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            state_json, checkpoint_id, timestamp = row
            checkpoint = StateCheckpoint.from_json(state_json)
            self._current_checkpoint_id = checkpoint_id

            return GraphState(**checkpoint.state)

    def get_latest_checkpoint_id(self, thread_id: str) -> str | None:
        """Get the latest checkpoint ID for a thread."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT checkpoint_id
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (thread_id,),
            )

            row = cursor.fetchone()
            conn.close()

            return row[0] if row else None

    def get_history(self, thread_id: str, limit: int = 10) -> list[CheckpointMetadata]:
        """
        Get checkpoint history for a thread.

        Args:
            thread_id: Thread/session identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata (newest first)
        """
        import json

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT checkpoint_id, parent_checkpoint_id, timestamp, state_json, metadata_json
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (thread_id, limit),
            )

            rows = cursor.fetchall()
            conn.close()

            history = []
            for row in rows:
                checkpoint_id, parent_id, timestamp, state_json, _ = row
                checkpoint = StateCheckpoint.from_json(state_json)

                history.append(
                    CheckpointMetadata(
                        thread_id=thread_id,
                        checkpoint_id=checkpoint_id,
                        parent_checkpoint_id=parent_id,
                        timestamp=timestamp,
                        state_keys=list(checkpoint.state.keys()),
                        state_size_bytes=len(state_json),
                    )
                )

            return history

    def get_thread_ids(self) -> list[str]:
        """Get all thread IDs with checkpoints."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT DISTINCT thread_id
                FROM checkpoints
                ORDER BY timestamp DESC
                """
            )

            rows = cursor.fetchall()
            conn.close()

            return [row[0] for row in rows]

    def delete_thread(self, thread_id: str) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread/session identifier

        Returns:
            Number of deleted checkpoints
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?",
                (thread_id,),
            )

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            _get_logger().info(
                "thread_deleted",
                thread_id=thread_id,
                checkpoints_deleted=deleted,
            )

            return deleted

    def clear(self) -> int:
        """Clear all checkpoints (use with caution)."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM checkpoints")
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM checkpoints")
            conn.commit()
            conn.close()

            _get_logger().warning("checkpoints_cleared", count=count)

            return count


# =============================================================================
# Global Singleton
# =============================================================================


_checkpointer: StateCheckpointer | None = None
_checkpointer_lock = threading.Lock()


def get_checkpointer() -> StateCheckpointer:
    """Get the global checkpointer instance."""
    global _checkpointer
    with _checkpointer_lock:
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
    "GraphState",
    "StateCheckpoint",
    "CheckpointMetadata",
    "StateCheckpointer",
    "get_checkpointer",
    "create_initial_state",
    "merge_state",
]
