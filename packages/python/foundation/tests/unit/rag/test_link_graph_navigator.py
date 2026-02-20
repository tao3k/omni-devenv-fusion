"""Tests for link_graph_navigator module routed by LinkGraph backend."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from omni.rag.link_graph.models import LinkGraphDirection
from omni.rag.link_graph_navigator import (
    LinkGraphNavigator,
    NavigationConfig,
    get_link_graph_navigator,
)


class _FakeBackend:
    def __init__(self) -> None:
        self.search_calls: list[tuple[str, int]] = []
        self.neighbor_calls: list[tuple[str, LinkGraphDirection, int, int]] = []

    async def search_planned(self, query: str, limit: int = 20):
        self.search_calls.append((query, limit))
        return {
            "query": query,
            "search_options": {},
            "hits": [
                SimpleNamespace(stem="python", title="Python", path="docs/python.md", score=0.9),
                SimpleNamespace(stem="rust", title="Rust", path="docs/rust.md", score=0.8),
            ],
        }

    async def metadata(self, stem: str):
        tags = {"python": ["skill", "lang"], "rust": ["lang"]}.get(stem, [])
        return SimpleNamespace(stem=stem, tags=tags)

    async def neighbors(
        self,
        stem: str,
        *,
        direction: LinkGraphDirection = LinkGraphDirection.BOTH,
        hops: int = 1,
        limit: int = 50,
    ):
        self.neighbor_calls.append((stem, direction, hops, limit))
        if stem == "python" and direction == LinkGraphDirection.OUTGOING:
            return [SimpleNamespace(stem="rust", title="Rust")]
        if stem == "python" and direction == LinkGraphDirection.INCOMING:
            return [SimpleNamespace(stem="guide", title="Guide")]
        if stem == "rust" and direction == LinkGraphDirection.INCOMING:
            return [SimpleNamespace(stem="python", title="Python")]
        return []


@pytest.mark.asyncio
async def test_get_holographic_context_uses_search_and_metadata() -> None:
    backend = _FakeBackend()
    navigator = LinkGraphNavigator(backend=backend, config=NavigationConfig(anchor_limit=2))
    xml = await navigator.get_holographic_context("lang query")

    assert "<knowledge_graph>" in xml
    assert 'id="python"' in xml
    assert "<tags>skill,lang</tags>" in xml
    assert backend.search_calls == [("lang query", 2)]


@pytest.mark.asyncio
async def test_get_holographic_context_empty_returns_empty_tag() -> None:
    class _EmptyBackend(_FakeBackend):
        async def search_planned(self, query: str, limit: int = 20):
            del query, limit
            return {"query": "", "search_options": {}, "hits": []}

    navigator = LinkGraphNavigator(backend=_EmptyBackend())
    xml = await navigator.get_holographic_context("none")
    assert "<empty/>" in xml


@pytest.mark.asyncio
async def test_get_subgraph_includes_incoming_and_outgoing_links() -> None:
    backend = _FakeBackend()
    navigator = LinkGraphNavigator(backend=backend)
    xml = await navigator.get_subgraph(["python"], max_backlinks=3, max_outlinks=3)

    assert "<knowledge_subgraph>" in xml
    assert "<referenced_by>" in xml
    assert "<references>" in xml
    assert 'id="guide"' in xml
    assert 'id="rust"' in xml


@pytest.mark.asyncio
async def test_get_related_context_traverses_levels() -> None:
    backend = _FakeBackend()
    navigator = LinkGraphNavigator(backend=backend)
    xml = await navigator.get_related_context("python", depth=2, limit_per_level=5)

    assert '<related_context center="python" depth="2">' in xml
    assert '<level n="0">' in xml
    assert '<level n="1">' in xml
    assert '<node id="python">' in xml


def test_format_as_xml_uses_payloads() -> None:
    navigator = LinkGraphNavigator(backend=_FakeBackend())
    xml = navigator.format_as_xml(
        anchors=[{"id": "python", "title": "Python", "preview": "doc"}],
        backlinks={"python": [{"id": "guide", "title": "Guide"}]},
        outlinks={"python": [{"id": "rust", "title": "Rust"}]},
    )

    assert "<knowledge_graph>" in xml
    assert "<referenced_by>" in xml
    assert "<references>" in xml
    assert "<preview>doc</preview>" in xml


def test_get_link_graph_navigator_factory_uses_common_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _FakeBackend()
    monkeypatch.setattr(
        "omni.rag.link_graph_navigator.get_link_graph_backend",
        lambda notebook_dir=None: backend,
    )
    nav = get_link_graph_navigator(notebook_dir="/tmp/notebook")
    assert isinstance(nav, LinkGraphNavigator)
    assert nav.backend is backend
