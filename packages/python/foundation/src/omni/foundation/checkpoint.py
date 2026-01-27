"""
checkpoint.py - Unified Checkpoint Storage using Rust LanceDB Backend

Provides persistent state storage for LangGraph workflows using the unified
Rust CheckpointStore implementation with LanceDB backend.

Architecture:
- Single LanceDB database at path from settings (default: .cache/checkpoints.lance)
- One table per workflow type (prefixed with "checkpoint_")
- Supports checkpoint versioning, search, and metadata

Usage:
    from omni.foundation.checkpoint import get_checkpointer, save_workflow_state, load_workflow_state

    # Get a checkpointer for a workflow type
    checkpointer = get_checkpointer("smart_commit")

    # Save state
    save_workflow_state("smart_commit", "workflow-123", {"status": "prepared", "files": [...]})

    # Load latest state
    state = load_workflow_state("smart_commit", "workflow-123")

LangGraph Integration:
    from omni.foundation.checkpoint import RustCheckpointSaver

    # Use as LangGraph checkpointer
    saver = RustCheckpointSaver(workflow_type="research")
    graph.compile(checkpointer=saver)
"""

from __future__ import annotations

import json
import time
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting

logger = get_logger("omni.foundation.checkpoint")

# Global store cache to avoid recreating PyCheckpointStore
_checkpoint_store_cache: dict[str, Any] = {}


def _get_store() -> Any:
    """Get or create the global PyCheckpointStore instance.

    Note: The Rust CheckpointStore reuses existing LanceDB files.
    This cache is per-process, so each new CLI invocation creates a new
    Python-side wrapper, but the underlying LanceDB data is persistent.
    """
    from omni.foundation.config.dirs import get_checkpoint_db_path

    db_path = str(get_checkpoint_db_path())

    if db_path not in _checkpoint_store_cache:
        try:
            # Import Rust bindings
            from omni_core_rs import PyCheckpointStore, create_checkpoint_store

            dimension = get_setting("checkpoint.embedding_dimension")
            _checkpoint_store_cache[db_path] = create_checkpoint_store(db_path, dimension)
            # Note: LanceDB reuses existing files; this just creates the Python wrapper
            logger.debug("Initialized checkpoint store wrapper", db_path=db_path)
        except ImportError as e:
            logger.warning(f"Rust bindings not available: {e}, using fallback SQLite")
            _checkpoint_store_cache[db_path] = None

    return _checkpoint_store_cache[db_path]


def _get_table_name(workflow_type: str) -> str:
    """Get the full table name for a workflow type."""
    from omni.foundation.config.dirs import get_checkpoint_table_name

    return get_checkpoint_table_name(workflow_type)


def get_checkpointer(workflow_type: str) -> Any:
    """Get a checkpointer for a specific workflow type.

    Args:
        workflow_type: Type of workflow (e.g., "smart_commit", "research")

    Returns:
        PyCheckpointStore instance for the workflow type
    """
    store = _get_store()
    if store is None:
        return None

    table_name = _get_table_name(workflow_type)
    return store


def save_workflow_state(
    workflow_type: str,
    workflow_id: str,
    state: dict[str, Any],
    parent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Save workflow state to checkpoint store.

    Args:
        workflow_type: Type of workflow (e.g., "smart_commit")
        workflow_id: Unique workflow identifier
        state: State dictionary to save
        parent_id: Parent checkpoint ID for versioning (optional)
        metadata: Optional metadata dict

    Returns:
        True if save succeeded
    """
    store = _get_store()
    if store is None:
        logger.warning("No checkpoint store available, state not persisted")
        return False

    try:
        table_name = _get_table_name(workflow_type)
        checkpoint_id = f"{workflow_id}-{int(time.time() * 1000)}"
        timestamp = time.time()
        content = json.dumps(state)
        metadata_json = json.dumps(metadata) if metadata else None

        store.save_checkpoint(
            table_name=table_name,
            checkpoint_id=checkpoint_id,
            thread_id=workflow_id,
            content=content,
            timestamp=timestamp,
            parent_id=parent_id,
            embedding=None,
            metadata=metadata_json,
        )

        logger.debug("Saved workflow state", workflow_type=workflow_type, workflow_id=workflow_id)
        return True

    except Exception as e:
        logger.error("Failed to save workflow state", error=str(e))
        return False


def load_workflow_state(workflow_type: str, workflow_id: str) -> dict[str, Any] | None:
    """Load the latest workflow state from checkpoint store.

    Args:
        workflow_type: Type of workflow
        workflow_id: Workflow identifier

    Returns:
        State dict or None if not found
    """
    store = _get_store()
    if store is None:
        return None

    try:
        table_name = _get_table_name(workflow_type)
        content = store.get_latest(table_name, workflow_id)

        if content:
            return json.loads(content)
        return None

    except Exception as e:
        logger.error("Failed to load workflow state", error=str(e))
        return None


def get_workflow_history(
    workflow_type: str,
    workflow_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get workflow state history (newest first).

    Args:
        workflow_type: Type of workflow
        workflow_id: Workflow identifier
        limit: Maximum number of checkpoints to return

    Returns:
        List of checkpoint dicts with content, metadata, and timestamp
    """
    store = _get_store()
    if store is None:
        return []

    try:
        table_name = _get_table_name(workflow_type)
        raw_history = store.get_history(table_name, workflow_id, limit)

        history = []
        for item in raw_history:
            try:
                checkpoint = json.loads(item)
                history.append(checkpoint)
            except json.JSONDecodeError:
                continue

        return history

    except Exception as e:
        logger.error("Failed to get workflow history", error=str(e))
        return []


def delete_workflow_state(workflow_type: str, workflow_id: str) -> bool:
    """Delete all checkpoints for a workflow.

    Args:
        workflow_type: Type of workflow
        workflow_id: Workflow identifier

    Returns:
        True if deletion succeeded
    """
    store = _get_store()
    if store is None:
        return False

    try:
        table_name = _get_table_name(workflow_type)
        count = store.delete_thread(table_name, workflow_id)
        logger.info(
            "Deleted workflow checkpoints",
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            count=count,
        )
        return True

    except Exception as e:
        logger.error("Failed to delete workflow state", error=str(e))
        return False


__all__ = [
    "get_checkpointer",
    "save_workflow_state",
    "load_workflow_state",
    "get_workflow_history",
    "delete_workflow_state",
]
