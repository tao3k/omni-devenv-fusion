"""Unit tests for MCP startup guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from omni.agent.mcp_server import startup


class _FakeThread:
    def __init__(self, alive: bool = True) -> None:
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


def test_wait_for_sse_server_readiness_raises_server_error() -> None:
    thread = _FakeThread(alive=True)
    server_error: list[Exception | None] = [RuntimeError("bind failed")]
    with pytest.raises(RuntimeError, match="failed to start"):
        startup.wait_for_sse_server_readiness(
            "127.0.0.1",
            3002,
            thread,
            server_error,
            timeout_seconds=0.05,
            poll_interval_seconds=0.001,
        )


def test_wait_for_sse_server_readiness_raises_when_thread_exits() -> None:
    thread = _FakeThread(alive=False)
    server_error: list[Exception | None] = [None]
    with pytest.raises(RuntimeError, match="thread exited"):
        startup.wait_for_sse_server_readiness(
            "127.0.0.1",
            3002,
            thread,
            server_error,
            timeout_seconds=0.05,
            poll_interval_seconds=0.001,
        )


def test_wait_for_sse_server_readiness_times_out() -> None:
    thread = _FakeThread(alive=True)
    server_error: list[Exception | None] = [None]
    with (
        patch("httpx.get", side_effect=RuntimeError("not ready")),
        pytest.raises(TimeoutError, match="health check timed out"),
    ):
        startup.wait_for_sse_server_readiness(
            "127.0.0.1",
            3002,
            thread,
            server_error,
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        )


def test_wait_for_sse_server_readiness_succeeds_on_healthy_response() -> None:
    thread = _FakeThread(alive=True)
    server_error: list[Exception | None] = [None]
    healthy_resp = SimpleNamespace(status_code=200)
    with patch("httpx.get", return_value=healthy_resp):
        startup.wait_for_sse_server_readiness(
            "127.0.0.1",
            3002,
            thread,
            server_error,
            timeout_seconds=0.05,
            poll_interval_seconds=0.001,
        )
