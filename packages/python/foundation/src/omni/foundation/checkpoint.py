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
    from omni.foundation.config.database import get_checkpoint_db_path

    db_path = str(get_checkpoint_db_path())

    if db_path not in _checkpoint_store_cache:
        try:
            from omni_core_rs import create_checkpoint_store
        except ImportError as e:
            raise RuntimeError(
                "Rust bindings (omni_core_rs) are required for checkpoint storage. "
                "Build/install omni-core-rs before running checkpoint workflows."
            ) from e

        dimension = get_setting("checkpoint.embedding_dimension")
        _checkpoint_store_cache[db_path] = create_checkpoint_store(db_path, dimension)
        # Note: LanceDB reuses existing files; this just creates the Python wrapper
        logger.debug("Initialized checkpoint store wrapper", db_path=db_path)

    return _checkpoint_store_cache[db_path]


def _get_table_name(workflow_type: str) -> str:
    """Get the full table name for a workflow type."""
    from omni.foundation.config.database import get_checkpoint_table_name

    return get_checkpoint_table_name(workflow_type)


def get_checkpointer(workflow_type: str) -> Any:
    """Get a checkpointer for a specific workflow type.

    Args:
        workflow_type: Type of workflow (e.g., "smart_commit", "research")

    Returns:
        PyCheckpointStore instance for the workflow type
    """
    _ = _get_table_name(workflow_type)
    return _get_store()


def get_checkpoint_schema_id() -> str:
    """Return checkpoint schema id for observability/debugging."""
    store = _get_store()
    schema_method = getattr(store, "checkpoint_schema_id", None)
    if callable(schema_method):
        return str(schema_method())

    # Fallback: Python schema API (same shared schema file)
    from omni.foundation.api.checkpoint_schema import get_schema_id

    return str(get_schema_id())


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

    try:
        from omni.foundation.api.checkpoint_schema import validate_checkpoint_write

        table_name = _get_table_name(workflow_type)
        checkpoint_id = f"{workflow_id}-{int(time.time() * 1000)}"
        timestamp = time.time()
        content = json.dumps(state)
        metadata_json = json.dumps(metadata) if metadata else None

        payload = {
            "checkpoint_id": checkpoint_id,
            "thread_id": workflow_id,
            "timestamp": timestamp,
            "content": content,
            "parent_id": parent_id,
            "embedding": None,
            "metadata": metadata_json,
        }
        validate_checkpoint_write(table_name, payload)

        store.save_checkpoint(
            table_name=table_name,
            checkpoint_id=payload["checkpoint_id"],
            thread_id=payload["thread_id"],
            content=payload["content"],
            timestamp=payload["timestamp"],
            parent_id=payload["parent_id"],
            embedding=payload["embedding"],
            metadata=payload["metadata"],
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

    try:
        table_name = _get_table_name(workflow_type)
        content = store.get_latest(table_name, workflow_id)

        if content:
            return json.loads(content)
        return None

    except Exception as e:
        table_name = _get_table_name(workflow_type)
        auto_repair = bool(get_setting("checkpoint.auto_repair_on_load", True))
        if auto_repair and hasattr(store, "cleanup_orphan_checkpoints"):
            try:
                removed = int(store.cleanup_orphan_checkpoints(table_name, False))
                logger.warning(
                    "Checkpoint load failed; auto-repair attempted",
                    workflow_type=workflow_type,
                    workflow_id=workflow_id,
                    removed=removed,
                    error=str(e),
                )
                content = store.get_latest(table_name, workflow_id)
                if content:
                    return json.loads(content)
                return None
            except Exception as repair_error:
                logger.error(
                    "Checkpoint auto-repair failed",
                    workflow_type=workflow_type,
                    workflow_id=workflow_id,
                    error=str(repair_error),
                )
        logger.error("Failed to load workflow state", error=str(e))
        return None


def repair_workflow_state(
    workflow_type: str,
    *,
    dry_run: bool = False,
    force_recover: bool = False,
) -> dict[str, Any]:
    """Run checkpoint repair workflow for a workflow table."""
    store = _get_store()
    table_name = _get_table_name(workflow_type)
    result: dict[str, Any] = {
        "workflow_type": workflow_type,
        "table_name": table_name,
        "dry_run": dry_run,
        "force_recover": force_recover,
        "schema_id": None,
        "removed_orphans": 0,
        "status": "success",
        "details": [],
    }

    try:
        result["schema_id"] = get_checkpoint_schema_id()
    except Exception as e:
        result["details"].append(f"schema_id_unavailable: {e}")

    try:
        if hasattr(store, "cleanup_orphan_checkpoints"):
            removed = int(store.cleanup_orphan_checkpoints(table_name, dry_run))
            result["removed_orphans"] = removed
            result["details"].append(f"cleanup_orphan_checkpoints removed={removed}")
        else:
            result["details"].append("cleanup_orphan_checkpoints unavailable in rust binding")

        if force_recover:
            if dry_run:
                result["details"].append("force_recover skipped because dry_run=true")
            elif hasattr(store, "force_recover_table"):
                store.force_recover_table(table_name)
                result["details"].append("force_recover_table executed")
            else:
                result["details"].append("force_recover_table unavailable in rust binding")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


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
    "delete_workflow_state",
    "get_checkpoint_schema_id",
    "get_checkpointer",
    "get_workflow_history",
    "load_workflow_state",
    "repair_workflow_state",
    "save_workflow_state",
]
