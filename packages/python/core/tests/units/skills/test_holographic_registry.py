"""Unit tests for HolographicRegistry search contracts."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from omni.core.skills.registry.holographic import HolographicRegistry


class _FakeEmbedder:
    dimension = 4

    def embed(self, text: str):
        return [[0.1, 0.2, 0.3, 0.4]]


@pytest.mark.asyncio
async def test_get_tool_uses_json_metadata_filter_and_scan_limit():
    store = MagicMock()
    store.search_optimized.return_value = [
        json.dumps(
            {
                "schema": "omni.vector.search.v1",
                "id": "tool.echo",
                "content": "Echo text",
                "metadata": {
                    "name": "tool.echo",
                    "module": "demo",
                    "file_path": "skills/demo.py",
                    "args": [],
                    "return_type": "str",
                },
                "distance": 0.1,
            }
        )
    ]

    registry = HolographicRegistry(vector_store=store, embedding_service=_FakeEmbedder())
    tool = await registry.get_tool("tool.echo")

    assert tool is not None
    assert tool.name == "tool.echo"

    store.search_optimized.assert_called_once()
    kwargs = store.search_optimized.call_args.kwargs
    assert kwargs["table_name"] == "skills_registry"
    assert kwargs["limit"] == 1

    options = json.loads(kwargs["options_json"])
    assert json.loads(options["where_filter"]) == {"name": "tool.echo"}
    assert options["scan_limit"] == 4096
