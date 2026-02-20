"""Unit tests for AgentMCPHandler embedding offload behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from omni.agent.server import AgentMCPHandler


def _build_handler(monkeypatch: pytest.MonkeyPatch) -> AgentMCPHandler:
    monkeypatch.setattr("omni.agent.server.get_kernel", lambda: SimpleNamespace())
    return AgentMCPHandler()


@pytest.mark.asyncio
async def test_handle_embed_texts_offloads_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _build_handler(monkeypatch)

    async def _run_in_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch(
            "omni.foundation.services.embedding.get_embedding_service",
            return_value=SimpleNamespace(dimension=3),
        ),
        patch(
            "omni.foundation.services.embedding.embed_batch",
            return_value=[[1.0, 2.0, 3.0]],
        ) as mock_embed_batch,
        patch("omni.agent.server.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        mock_to_thread.side_effect = _run_in_thread
        response = await handler._handle_embed_texts(11, {"texts": ["hello"]})

    assert response["id"] == 11
    assert response.get("error") is None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["count"] == 1
    assert payload["dimension"] == 3
    assert payload["vectors"] == [[1.0, 2.0, 3.0]]
    mock_embed_batch.assert_called_once_with(["hello"])
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
async def test_handle_embed_single_offloads_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _build_handler(monkeypatch)

    async def _run_in_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch(
            "omni.foundation.services.embedding.get_embedding_service",
            return_value=SimpleNamespace(dimension=3),
        ),
        patch(
            "omni.foundation.services.embedding.embed_text",
            return_value=[0.1, 0.2, 0.3],
        ) as mock_embed_text,
        patch("omni.agent.server.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
    ):
        mock_to_thread.side_effect = _run_in_thread
        response = await handler._handle_embed_single(12, {"text": "hello"})

    assert response["id"] == 12
    assert response.get("error") is None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["dimension"] == 3
    assert payload["vector"] == [0.1, 0.2, 0.3]
    mock_embed_text.assert_called_once_with("hello")
    assert mock_to_thread.await_count == 1
