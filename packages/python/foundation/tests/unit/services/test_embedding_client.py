"""Unit tests for embedding HTTP client sync wrappers."""

from __future__ import annotations

import json
from unittest.mock import patch

from omni.foundation.embedding_client import EmbeddingClient


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self.status = 200
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_sync_embed_batch_uses_sync_http_path():
    client = EmbeddingClient(base_url="http://127.0.0.1:18501")
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeHTTPResponse({"vectors": [[0.1, 0.2], [0.3, 0.4]]}),
    ) as mock_urlopen:
        vectors = client.sync_embed_batch(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert mock_urlopen.call_count == 1


def test_sync_embed_uses_sync_http_path():
    client = EmbeddingClient(base_url="http://127.0.0.1:18501")
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeHTTPResponse({"vector": [0.9, 0.8]}),
    ) as mock_urlopen:
        vectors = client.sync_embed("hello")

    assert vectors == [[0.9, 0.8]]
    assert mock_urlopen.call_count == 1
