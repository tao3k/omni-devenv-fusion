"""
omni.langgraph.checkpoint.lance - Rust-Native Checkpointer for LangGraph

High-performance state management backed by omni-vector (LanceDB).
Implements LangGraph's BaseCheckpointSaver interface with Rust bindings.

Features:
- Global Connection Pooling (via Rust Singleton)
- Predicate Push-down filtering
- Event-driven checkpoint notifications
- Zero-copy reads

Usage:
    from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

    checkpointer = RustLanceCheckpointSaver()
    app = workflow.compile(checkpointer=checkpointer)
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Optional

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.langgraph.checkpoint.rust")

# Try to import Rust bindings
try:
    import omni_core_rs as _rust

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    _rust = None  # type: ignore


def _json_dumps(obj: Any) -> str:
    """Serialize to JSON string."""
    return json.dumps(obj, default=str)


def _json_loads(s: str) -> Any:
    """Deserialize from JSON string."""
    return json.loads(s)


class RustLanceCheckpointSaver(BaseCheckpointSaver):
    """
    A LangGraph CheckpointSaver that delegates to the Rust 'omni-vector' crate.

    Features:
    - Global Connection Pooling (via Rust Singleton) - No multiple initialization
    - Predicate Push-down filtering for efficient queries
    - Event Bus notifications on checkpoint save
    - Millisecond-level state存取

    Architecture:
    ```
    LangGraph.workflow.compile(checkpointer=RustLanceCheckpointSaver())
                    │
                    ▼
    RustLanceCheckpointSaver.aput() / aget_tuple()
                    │
                    ▼
    omni_core_rs.create_checkpoint_store()  [Global Pool]
                    │
                    ▼
    omni_vector.CheckpointStore (LanceDB)
    ```
    """

    def __init__(
        self,
        base_path: str | None = None,
        table_name: str = "checkpoints",
        notify_on_save: bool = True,
    ):
        """
        Initialize the Rust-native checkpointer.

        Args:
            base_path: Path to LanceDB directory (auto-generated if not provided)
            table_name: Table name for checkpoint isolation (default: "checkpoints")
            notify_on_save: Whether to broadcast events on checkpoint save
        """
        # Note: We don't pass serializer to parent - LangGraph's BaseCheckpointSaver
        # handles serialization internally. We use self.json_dumps/loads which are
        # inherited from the parent class.

        if not RUST_AVAILABLE:
            raise RuntimeError(
                "Rust bindings (omni_core_rs) not available. "
                "Please build the Rust bindings first: just build-rust-dev"
            )

        if base_path is None:
            from omni.foundation.config.database import get_checkpoint_db_path

            base_path = str(get_checkpoint_db_path())

        self._table_name = table_name
        self._notify_on_save = notify_on_save

        # Initialize Rust Store (uses global connection pool - no duplicate init)
        logger.debug(f"🔌 Connecting to Rust Checkpoint Store at {base_path}...")
        self._store = _rust.create_checkpoint_store(base_path, 1536)
        logger.info(f"🧠 Rust Checkpoint Store initialized: {table_name}")

    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save a checkpoint to LanceDB via Rust.

        Args:
            config: RunnableConfig with thread_id and optional checkpoint_id
            checkpoint: Checkpoint dict (LangGraph format)
            metadata: Checkpoint metadata dict
            new_versions: Channel versions from LangGraph

        Returns:
            Updated config with checkpoint_id
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]

        # Ensure metadata contains step for LangGraph 1.0+ recovery
        if "step" not in metadata:
            metadata = dict(metadata)
            # Try to get step from checkpoint's versions_seen or default to 0
            step = checkpoint.get("versions_seen", {}).get("__root__", 0)
            metadata["step"] = step

        # Serialize checkpoint and metadata
        content = _json_dumps(checkpoint)
        metadata_json = _json_dumps(metadata)

        # Get parent checkpoint ID from config
        parent_id = config.get("configurable", {}).get("checkpoint_id")

        # Get timestamp from checkpoint or metadata (convert ISO string to float)
        ts_value = checkpoint.get("ts") or metadata.get("ts")
        if isinstance(ts_value, str):
            # Parse ISO timestamp string to float
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
                timestamp = dt.timestamp()
            except (ValueError, AttributeError):
                timestamp = 0.0
        elif isinstance(ts_value, (int, float)):
            timestamp = float(ts_value)
        else:
            timestamp = 0.0

        # Call Rust store (blocking call wrapped in async)
        # Uses global connection pool - no performance penalty
        self._store.save_checkpoint(
            table_name=self._table_name,
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            content=content,
            timestamp=timestamp,
            parent_id=parent_id,
            embedding=None,  # Checkpoints typically don't have embeddings
            metadata=metadata_json,
        )

        logger.debug(
            "💾 Checkpoint saved via Rust",
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
        )

        # Event Bus notification (optional, for monitoring)
        if self._notify_on_save:
            self._publish_checkpoint_event(thread_id, checkpoint_id, checkpoint)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        Retrieve a checkpoint tuple from LanceDB via Rust.

        Args:
            config: RunnableConfig with thread_id and optional checkpoint_id

        Returns:
            CheckpointTuple or None if not found
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        content: Optional[str]

        if checkpoint_id:
            # Get specific checkpoint by ID
            content = self._store.get_by_id(self._table_name, checkpoint_id)
        else:
            # Get latest checkpoint for thread (predicate push-down optimized)
            content = self._store.get_latest(self._table_name, thread_id)

        if not content:
            return None

        # Deserialize checkpoint
        checkpoint = _json_loads(content)

        # Reconstruct parent_config from stored parent_id
        # We need to fetch parent to build the chain
        parent_id = checkpoint.get("parent_id")
        parent_config = None
        if parent_id:
            parent_content = self._store.get_by_id(self._table_name, parent_id)
            if parent_content:
                parent_checkpoint = _json_loads(parent_content)
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": parent_id,
                    }
                }

        # Return tuple - metadata embedded in checkpoint for simplicity
        # LangGraph expects metadata in CheckpointTuple
        metadata = checkpoint.get("_metadata", {})

        # Ensure metadata contains step for LangGraph 1.0+ recovery
        if not isinstance(metadata, dict):
            metadata = {}
        if "step" not in metadata:
            # Try to extract step from checkpoint or default to 0
            step = checkpoint.get("versions_seen", {}).get("__root__", 0)
            if not isinstance(step, int):
                step = 0
            metadata = dict(metadata)
            metadata["step"] = step

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
        )

    async def alist(
        self,
        config: Dict[str, Any],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        List checkpoint history for a thread.

        Args:
            config: RunnableConfig with thread_id
            filter: Optional metadata filter (not fully supported)
            before: Optional checkpoint ID to list before
            limit: Maximum number of checkpoints to return

        Yields:
            CheckpointTuple for each historical checkpoint
        """
        thread_id = config["configurable"]["thread_id"]
        limit = limit or 10

        # Get history from Rust store
        history_contents = self._store.get_history(self._table_name, thread_id, limit)

        for content in history_contents:
            checkpoint = _json_loads(content)

            # Reconstruct minimal config for this checkpoint
            checkpoint_id = checkpoint["id"]
            checkpoint_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                }
            }

            metadata = checkpoint.get("_metadata", {})

            # Ensure metadata contains step for LangGraph 1.0+ recovery
            if not isinstance(metadata, dict):
                metadata = {}
            if "step" not in metadata:
                step = checkpoint.get("versions_seen", {}).get("__root__", 0)
                if not isinstance(step, int):
                    step = 0
                metadata = dict(metadata)
                metadata["step"] = step

            yield CheckpointTuple(
                config=checkpoint_config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
            )

    async def adelete_thread(self, thread_id: str) -> None:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread ID to delete
        """
        count = self._store.delete_thread(self._table_name, thread_id)
        logger.info(f"🗑️ Deleted {count} checkpoints for thread: {thread_id}")

    def _publish_checkpoint_event(
        self, thread_id: str, checkpoint_id: str, checkpoint: Checkpoint
    ) -> None:
        """
        Publish checkpoint event to Rust Event Bus for monitoring.

        Args:
            thread_id: Thread identifier
            checkpoint_id: Checkpoint ID
            checkpoint: Checkpoint content
        """
        try:
            from omni_core_rs import PyGlobalEventBus

            payload = json.dumps(
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "step": checkpoint.get("step", 0),
                    "ts": checkpoint.get("ts", 0.0),
                }
            )

            PyGlobalEventBus.publish("langgraph", "checkpoint/saved", payload)
            logger.debug(f"📡 Published checkpoint event: {checkpoint_id}")

        except ImportError:
            logger.debug("Rust Event Bus not available, skipping notification")
        except Exception as e:
            logger.warning(f"Failed to publish checkpoint event: {e}")

    @property
    def table_name(self) -> str:
        """Get the table name."""
        return self._table_name

    @property
    def store(self) -> Any:
        """Get the underlying Rust store for advanced operations."""
        return self._store

    def count(self, thread_id: str) -> int:
        """Count checkpoints for a thread."""
        return self._store.count(self._table_name, thread_id)


def create_checkpointer(
    base_path: str | None = None,
    table_name: str = "checkpoints",
    notify_on_save: bool = True,
) -> RustLanceCheckpointSaver:
    """
    Factory function to create a Rust-native checkpointer.

    Args:
        base_path: Optional custom path for LanceDB
        table_name: Table name for checkpoint isolation
        notify_on_save: Whether to broadcast events on save

    Returns:
        Configured RustLanceCheckpointSaver instance
    """
    return RustLanceCheckpointSaver(
        base_path=base_path,
        table_name=table_name,
        notify_on_save=notify_on_save,
    )


__all__ = ["RustLanceCheckpointSaver", "create_checkpointer"]
