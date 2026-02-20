"""MCP startup guards and initialization helpers.

Core startup logic lives here so CLI command modules stay thin.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omni.agent.server import AgentMCPHandler


def initialize_handler_on_server_loop(
    handler: AgentMCPHandler,
    loop: asyncio.AbstractEventLoop,
    *,
    timeout_seconds: float = 30.0,
) -> None:
    """Initialize MCP handler on the long-lived SSE server event loop."""
    future = asyncio.run_coroutine_threadsafe(handler.initialize(), loop)
    try:
        future.result(timeout=timeout_seconds)
    except FutureTimeoutError as e:
        future.cancel()
        raise TimeoutError(f"Timed out initializing MCP handler after {timeout_seconds}s") from e


def wait_for_sse_server_readiness(
    host: str,
    port: int,
    server_thread: Any,
    server_error: list[Exception | None],
    *,
    timeout_seconds: float = 5.0,
    health_timeout_seconds: float = 0.5,
    poll_interval_seconds: float = 0.1,
) -> None:
    """Wait until SSE /health is reachable, failing fast on startup errors.

    Raises:
        RuntimeError: If server thread exits early or reported startup failure.
        TimeoutError: If /health never becomes ready within timeout_seconds.
    """
    import httpx

    deadline = time.monotonic() + timeout_seconds
    health_url = f"http://{host}:{port}/health"
    while time.monotonic() < deadline:
        if server_error[0] is not None:
            raise RuntimeError(f"SSE server failed to start: {server_error[0]}") from server_error[
                0
            ]
        if not server_thread.is_alive():
            raise RuntimeError("SSE server thread exited before health became ready")

        try:
            resp = httpx.get(health_url, timeout=health_timeout_seconds)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(poll_interval_seconds)

    if server_error[0] is not None:
        raise RuntimeError(f"SSE server failed to start: {server_error[0]}") from server_error[0]
    raise TimeoutError(f"SSE server health check timed out after {timeout_seconds:.1f}s")
