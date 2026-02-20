"""Tests for MCP embedding warmup behavior."""

from __future__ import annotations

import time

import pytest

from omni.agent.cli.commands import mcp as mcp_cmd


@pytest.mark.asyncio
async def test_warm_embedding_timeout_does_not_block(monkeypatch):
    class _SlowService:
        backend = "litellm"

        def __init__(self):
            self.calls = 0

        def embed(self, _text: str):
            self.calls += 1
            time.sleep(0.5)
            return [[0.0]]

    service = _SlowService()
    monkeypatch.setattr(
        "omni.foundation.services.embedding.get_embedding_service",
        lambda: service,
    )

    start = time.perf_counter()
    await mcp_cmd._warm_embedding_after_startup(timeout_seconds=0.01)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2
    assert service.calls == 1


@pytest.mark.asyncio
async def test_warm_embedding_skips_unavailable_backend(monkeypatch):
    class _UnavailableService:
        backend = "unavailable"

        def embed(self, _text: str):
            raise AssertionError("embed should not be called for unavailable backend")

    monkeypatch.setattr(
        "omni.foundation.services.embedding.get_embedding_service",
        lambda: _UnavailableService(),
    )

    await mcp_cmd._warm_embedding_after_startup(timeout_seconds=0.01)


@pytest.mark.asyncio
async def test_warm_embedding_retries_transient_connection_error(monkeypatch):
    class _FlakyService:
        backend = "litellm"

        def __init__(self):
            self.calls = 0

        def embed(self, _text: str):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError(
                    "litellm.APIConnectionError: OllamaException - "
                    "Server disconnected without sending a response."
                )
            return [[0.0]]

    service = _FlakyService()
    monkeypatch.setattr(
        "omni.foundation.services.embedding.get_embedding_service",
        lambda: service,
    )

    await mcp_cmd._warm_embedding_after_startup(
        timeout_seconds=1.0,
        max_attempts=3,
        retry_delay_seconds=0.0,
    )
    assert service.calls == 3


@pytest.mark.asyncio
async def test_warm_embedding_does_not_retry_non_transient_error(monkeypatch):
    class _BrokenService:
        backend = "litellm"

        def __init__(self):
            self.calls = 0

        def embed(self, _text: str):
            self.calls += 1
            raise RuntimeError("invalid embedding payload")

    service = _BrokenService()
    monkeypatch.setattr(
        "omni.foundation.services.embedding.get_embedding_service",
        lambda: service,
    )

    await mcp_cmd._warm_embedding_after_startup(
        timeout_seconds=1.0,
        max_attempts=4,
        retry_delay_seconds=0.0,
    )
    assert service.calls == 1
