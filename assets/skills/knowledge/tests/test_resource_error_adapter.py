"""Tests for knowledge skill resource error payload adapters."""

from __future__ import annotations

import sys
import types

import link_graph_search
import pytest
from graph import graph_stats_resource


@pytest.mark.asyncio
async def test_link_graph_stats_resource_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_backend():
        raise RuntimeError("link graph backend boom")

    monkeypatch.setattr(link_graph_search, "_get_link_graph_backend", _raise_backend)

    out = await link_graph_search.link_graph_stats_resource()

    assert out == {"error": "link graph backend boom"}


def test_graph_stats_resource_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_store():
        raise RuntimeError("graph backend boom")

    fake_graph = types.SimpleNamespace(get_graph_store=_raise_store)
    monkeypatch.setitem(sys.modules, "omni.rag.graph", fake_graph)

    out = graph_stats_resource()

    assert out == {"error": "graph backend boom"}
