"""
pipeline_checkpoint.py - Checkpointer utilities for pipeline runtime assembly.
"""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.tracer.pipeline")


def create_in_memory_checkpointer() -> Any | None:
    """Create LangGraph MemorySaver checkpointer if available."""
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("memory_saver_unavailable", error=str(exc))
        return None
    return MemorySaver()


def compile_workflow(
    workflow: Any,
    *,
    checkpointer: Any | None = None,
    use_memory_saver: bool = False,
) -> Any:
    """Compile a workflow with optional checkpointer injection."""
    active_checkpointer = checkpointer
    if active_checkpointer is None and use_memory_saver:
        active_checkpointer = create_in_memory_checkpointer()

    if active_checkpointer is not None:
        return workflow.compile(checkpointer=active_checkpointer)
    return workflow.compile()


__all__ = [
    "create_in_memory_checkpointer",
    "compile_workflow",
]
