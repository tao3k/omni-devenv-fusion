"""Unit tests for MCP embedding tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from omni.agent.mcp_server.tools.embedding import register_embedding_tools


class _FakeApp:
    def __init__(self) -> None:
        self.tools: dict[str, callable] = {}

    def call_tool(self):
        def _decorator(func):
            self.tools[func.__name__] = func
            return func

        return _decorator


class _FakeEmbedService:
    @staticmethod
    def embed_batch(texts: list[str]) -> list[list[float]]:
        return [[float(i)] * 3 for i, _ in enumerate(texts, start=1)]

    @staticmethod
    def embed(text: str) -> list[list[float]]:
        _ = text
        return [[0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_embed_texts_uses_thread_offload() -> None:
    app = _FakeApp()
    register_embedding_tools(app)

    async def _run_in_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch(
            "omni.foundation.services.embedding.get_embedding_service",
            return_value=_FakeEmbedService(),
        ),
        patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        mock_to_thread.side_effect = _run_in_thread
        result = await app.tools["embed_texts"]({"texts": ["a", "b"]})

    assert len(result) == 1
    vectors = json.loads(result[0].text)
    assert vectors == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_embed_single_uses_thread_offload() -> None:
    app = _FakeApp()
    register_embedding_tools(app)

    async def _run_in_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch(
            "omni.foundation.services.embedding.get_embedding_service",
            return_value=_FakeEmbedService(),
        ),
        patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        mock_to_thread.side_effect = _run_in_thread
        result = await app.tools["embed_single"]({"text": "hello"})

    assert len(result) == 1
    vector = json.loads(result[0].text)
    assert vector == [0.1, 0.2, 0.3]
    assert mock_to_thread.await_count == 1
