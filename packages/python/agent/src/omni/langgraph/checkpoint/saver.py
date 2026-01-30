"""
omni/langgraph/checkpoint/saver.py - LangGraph Checkpoint Saver

LangGraph-compatible checkpoint saver using Rust LanceDB backend:
- RustCheckpointSaver: BaseCheckpointSaver implementation for LangGraph
- get_default_checkpointer(): Global singleton for shared instance

Usage:
    from omni.langgraph.checkpoint.saver import RustCheckpointSaver, get_default_checkpointer

    # Shared singleton (recommended for most cases)
    saver = get_default_checkpointer()
    graph.compile(checkpointer=saver)

    # Custom table (creates new instance if needed)
    saver = RustCheckpointSaver(table_name="my_workflow")
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

# Module-level cache for LanceCheckpointer instances to avoid repeated initialization
_CHECKPOINTER_CACHE: dict[tuple[str, int], LanceCheckpointer] = {}

# Global default checkpointer singleton
_default_checkpointer: "RustCheckpointSaver | None" = None


def get_default_checkpointer() -> "RustCheckpointSaver":
    """Get the global default RustCheckpointSaver singleton.

    This function returns a shared instance to avoid repeated LanceDB initialization.
    All skill workflows and the kernel should use this function for optimal performance.

    Returns:
        RustCheckpointSaver instance configured for default table

    Example:
        from omni.langgraph.checkpoint.saver import get_default_checkpointer

        saver = get_default_checkpointer()
        graph.compile(checkpointer=saver)
    """
    global _default_checkpointer
    if _default_checkpointer is None:
        _default_checkpointer = RustCheckpointSaver(table_name="checkpoints", dimension=1536)
        logger.info(f"RustCheckpointSaver initialized (singleton): {id(_default_checkpointer)}")
    return _default_checkpointer


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

        Uses module-level cache to avoid repeated LanceDB initialization.
        Multiple instances with same (table_name, dimension) share the same checkpointer.
        URI is determined by the first instance.

        Args:
            table_name: Table name for checkpoints (default: "checkpoints")
            uri: Path to LanceDB directory (auto-generated if not provided)
            dimension: Embedding dimension for semantic search
        """
        super().__init__()
        self._table_name = table_name

        # Use cache to avoid repeated initialization
        # Cache key: (table_name, dimension) - ignore URI, use first instance's URI
        cache_key = (table_name, dimension)
        if cache_key not in _CHECKPOINTER_CACHE:
            logger.debug(f"Creating new LanceCheckpointer for {table_name} (dim={dimension})")
            _CHECKPOINTER_CACHE[cache_key] = LanceCheckpointer(
                base_path=uri, table_name=table_name, notify_on_save=False
            )
        else:
            logger.debug(f"Reusing cached LanceCheckpointer for {table_name}")

        self._checkpointer = _CHECKPOINTER_CACHE[cache_key]

    @property
    def config_specs(self):
        """Return configuration specifications for the checkpointer."""
        return []

    async def aget_tuple(self, config: dict) -> CheckpointTuple | None:
        """Async get checkpoint tuple (config, checkpoint, metadata) for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        # Use the async method from LanceCheckpointer
        result = await self._checkpointer.aget_tuple(config)
        return result

    async def aput(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict,
        new_versions: dict,
    ) -> dict:
        """Async save a checkpoint."""
        # Delegate to LanceCheckpointer's aput
        await self._checkpointer.aput(config, checkpoint, metadata, new_versions)
        return config

    async def alist(
        self,
        config: dict | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Async list checkpoints for a config."""
        # Delegate to LanceCheckpointer's alist
        async for tuple in self._checkpointer.alist(config, filter=filter, before=before, limit=limit):
            yield tuple

    async def adelete_thread(self, thread_id: str) -> None:
        """Async delete all checkpoints for a thread."""
        await self._checkpointer.adelete_thread(thread_id)

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
