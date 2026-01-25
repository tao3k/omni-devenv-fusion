"""
omni/langgraph/checkpoint/saver.py - LangGraph Checkpoint Saver

LangGraph-compatible checkpoint saver using Rust LanceDB backend:
- RustCheckpointSaver: BaseCheckpointSaver implementation for LangGraph

Usage:
    from omni.langgraph.checkpoint.saver import RustCheckpointSaver

    saver = RustCheckpointSaver()
    graph.compile(checkpointer=saver)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from langgraph.checkpoint.base.id import uuid6

from omni.foundation.config.logging import get_logger
from omni.langgraph.checkpoint.lance import LanceCheckpointer

logger = get_logger("omni.langgraph.checkpoint.saver")

# Checkpoint version (matches LangGraph 1.0+)
LATEST_VERSION = 2


def _make_checkpoint(
    state: dict,
    checkpoint_id: str | None = None,
) -> dict:
    """Create a checkpoint dict with standard LangGraph 1.0+ structure."""
    return {
        "v": LATEST_VERSION,
        "id": checkpoint_id or uuid6().hex,
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel_values": state,
        "channel_versions": {},
        "versions_seen": {},
        "updated_channels": None,
    }


class RustCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph-compatible checkpoint saver using Rust LanceDB backend.

    Wraps LanceCheckpointer to implement the BaseCheckpointSaver interface
    required by LangGraph for graph checkpoint persistence.

    Usage:
        from omni.langgraph.checkpoint.saver import RustCheckpointSaver

        saver = RustCheckpointSaver()
        graph.compile(checkpointer=saver)

        # Or with custom table name
        saver = RustCheckpointSaver(table_name="research_graph")
    """

    def __init__(
        self,
        table_name: str = "checkpoints",
        uri: Path | str | None = None,
        dimension: int = 1536,
    ):
        """
        Initialize the Rust checkpoint saver.

        Args:
            table_name: Table name for checkpoints (default: "checkpoints")
            uri: Path to LanceDB directory (auto-generated if not provided)
            dimension: Embedding dimension for semantic search
        """
        super().__init__()
        self._table_name = table_name
        self._checkpointer = LanceCheckpointer(uri=uri, dimension=dimension)

    @property
    def config_specs(self):
        """Return configuration specifications for the checkpointer."""
        return []

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        """Get checkpoint tuple (config, checkpoint, metadata) for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        state = self._checkpointer.get(thread_id)
        if state:
            checkpoint = _make_checkpoint(state)
            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata={"source": None, "step": -1, "writes": {}},
            )
        return None

    def put(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict,
        new_versions: dict,
    ) -> dict:
        """Save a checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return config

        # Extract state from checkpoint (LangGraph 1.0+ format)
        if isinstance(checkpoint, dict):
            state = checkpoint.get("channel_values") or checkpoint.get("data") or checkpoint
            checkpoint_id = checkpoint.get("id", uuid6().hex)
        else:
            state = getattr(checkpoint, "channel_values", None) or getattr(
                checkpoint, "data", checkpoint
            )
            checkpoint_id = getattr(checkpoint, "id", uuid6().hex)

        logger.debug(
            "Saving checkpoint",
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            state_keys=list(state.keys()) if isinstance(state, dict) else [],
        )

        self._checkpointer.put(
            thread_id=thread_id,
            state=state,
            checkpoint_id=checkpoint_id,
            metadata={
                "source": metadata.get("source")
                if hasattr(metadata, "get")
                else getattr(metadata, "source", None),
                "step": metadata.get("step")
                if hasattr(metadata, "get")
                else getattr(metadata, "step", -1),
                "writes": metadata.get("writes")
                if hasattr(metadata, "get")
                else getattr(metadata, "writes", {}),
            },
        )

        return config

    def list(
        self,
        config: dict | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> list[CheckpointTuple]:
        """List checkpoints for a config."""
        thread_id = config.get("configurable", {}).get("thread_id") if config else None
        if not thread_id:
            return []

        limit = limit or 10
        history = self._checkpointer.get_history(thread_id, limit=limit)

        return [
            CheckpointTuple(
                config=config or {"configurable": {"thread_id": thread_id}},
                checkpoint=_make_checkpoint(state),
                metadata={"source": None, "step": -1, "writes": {}},
            )
            for state in history
        ]

    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints for a thread."""
        self._checkpointer.delete(thread_id)

    # Async methods - delegate to sync versions (BaseCheckpointSaver pattern)
    async def aget_tuple(self, config: dict) -> CheckpointTuple | None:
        """Async get checkpoint tuple."""
        return self.get_tuple(config)

    async def aput(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict,
        new_versions: dict,
    ) -> dict:
        """Async save a checkpoint."""
        return self.put(config, checkpoint, metadata, new_versions)

    async def alist(
        self,
        config: dict | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Async list checkpoints."""
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def adelete_thread(self, thread_id: str) -> None:
        """Async delete all checkpoints for a thread."""
        self.delete_thread(thread_id)

    # Optional: put_writes not implemented for LanceDB
    def put_writes(
        self,
        config: dict,
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Put writes (not implemented for LanceDB)."""
        pass

    async def aput_writes(
        self,
        config: dict,
        writes: list[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Async put writes (not implemented for LanceDB)."""
        pass


__all__ = ["RustCheckpointSaver"]
