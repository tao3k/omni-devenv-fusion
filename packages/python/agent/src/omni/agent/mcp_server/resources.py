"""
MCP resource reader helpers.

Reads project context (Sniffer), agent memory (Checkpoint), and system stats
from Rust-backed components.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from typing import Any, Callable

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.agent.mcp_server.resources")


def read_project_context(kernel: Any) -> str:
    """Read project context from Sniffer.

    Args:
        kernel: Initialized OmniKernel instance.

    Returns:
        JSON string with detected contexts.
    """
    try:
        sniffer = getattr(kernel, "router", None)
        if sniffer and hasattr(sniffer, "sniffer"):
            sniffer_instance = sniffer.sniffer
            if hasattr(sniffer_instance, "_active_contexts"):
                contexts = list(sniffer_instance._active_contexts)
            else:
                contexts = sniffer_instance.sniff(".") or []
        else:
            contexts = []

        return json.dumps(
            {
                "contexts": contexts,
                "timestamp": time.time(),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def read_agent_memory(kernel: Any) -> str:
    """Read latest agent state from Checkpoint Store.

    Args:
        kernel: Initialized OmniKernel instance.

    Returns:
        JSON string with checkpoint data.
    """
    try:
        if not kernel or not kernel.is_ready:
            return json.dumps({"error": "Kernel not ready"}, indent=2)

        from omni.foundation.config.database import get_checkpoint_db_path
        from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

        db_path = get_checkpoint_db_path()
        checkpointer = RustLanceCheckpointSaver(
            base_path=str(db_path),
            table_name="agent_checkpoints",
            notify_on_save=False,
        )

        config = {"configurable": {"thread_id": "mcp_session"}}
        tuple_data = checkpointer.get_tuple(config)

        if tuple_data:
            return json.dumps(
                {
                    "checkpoint": tuple_data.checkpoint,
                    "metadata": tuple_data.metadata,
                    "timestamp": time.time(),
                },
                indent=2,
                default=str,
            )

        return json.dumps({"status": "empty", "timestamp": time.time()}, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def get_process_memory_mb() -> float | None:
    """Current process RSS in MiB (for monitoring). ru_maxrss: bytes on macOS, KB on Linux."""
    try:
        r = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(r, "ru_maxrss", 0) or 0
        if sys.platform == "darwin":
            return round(rss / (1024 * 1024), 2)
        return round(rss / 1024, 2)  # Linux: already KB
    except Exception:
        return None


def _get_process_rss_mb() -> float | None:
    """Alias for get_process_memory_mb used by read_system_stats."""
    return get_process_memory_mb()


def read_system_stats(kernel: Any, start_time: float) -> str:
    """Read system statistics.

    Args:
        kernel: Initialized OmniKernel instance.
        start_time: Server start timestamp (``time.time()``).

    Returns:
        JSON string with uptime, tool count, memory_mb (RSS), etc.
    """
    try:
        uptime = time.time() - start_time

        tool_count = 0
        if kernel and kernel.is_ready:
            tool_count = len(kernel.skill_context.get_core_commands())

        payload: dict[str, Any] = {
            "uptime_seconds": round(uptime, 2),
            "tool_count": tool_count,
            "kernel_ready": kernel.is_ready if kernel else False,
            "version": "2.0.0",
        }
        rss_mb = _get_process_rss_mb()
        if rss_mb is not None:
            payload["memory_mb"] = rss_mb
            payload["memory_note"] = (
                "RSS; expect ~1–2G with minimal embedding + bounded vector cache"
            )

        return json.dumps(payload, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# =============================================================================
# Dynamic Resource Registration - For 10,000+ skills
# =============================================================================

# Registry for dynamically registered resources
_DYNAMIC_RESOURCES: dict[str, Callable] = {}


def register_dynamic_resource(uri: str, fn: Callable) -> None:
    """Register a dynamic resource function.

    Args:
        uri: Resource URI (e.g., "omni://skill/{skill_name}/context")
        fn: Callable that returns resource content
    """
    _DYNAMIC_RESOURCES[uri] = fn
    logger.debug(f"Registered dynamic resource: {uri}")


def unregister_dynamic_resource(uri: str) -> bool:
    """Unregister a dynamic resource.

    Args:
        uri: Resource URI to remove.

    Returns:
        True if removed, False if not found.
    """
    if uri in _DYNAMIC_RESOURCES:
        del _DYNAMIC_RESOURCES[uri]
        logger.debug(f"Unregistered dynamic resource: {uri}")
        return True
    return False


def list_dynamic_resources() -> list[str]:
    """List all registered dynamic resource URIs."""
    return list(_DYNAMIC_RESOURCES.keys())


async def read_dynamic_resource(uri: str) -> str:
    """Read content from a dynamic resource.

    Args:
        uri: Resource URI.

    Returns:
        Resource content or error message.
    """
    if uri not in _DYNAMIC_RESOURCES:
        return json.dumps({"error": f"Dynamic resource not found: {uri}"}, indent=2)

    try:
        fn = _DYNAMIC_RESOURCES[uri]
        if callable(fn):
            result = fn()
            # Handle async functions
            import asyncio

            if asyncio.iscoroutine(result):
                result = await result
            return result if isinstance(result, str) else json.dumps(result, indent=2)
        return json.dumps({"error": "Invalid resource function"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)
