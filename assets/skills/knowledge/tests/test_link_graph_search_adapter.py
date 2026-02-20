"""Unit tests for link_graph_search command adapters backed by LinkGraph API."""

from __future__ import annotations

import sys
import types

import link_graph_search
import pytest


class _FakeDirection:
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


class _FakeBackend:
    def __init__(self) -> None:
        self.neighbors_calls: list[tuple[str, str, int, int]] = []
        self.related_calls: list[tuple[str, int, int]] = []
        self.toc_calls: list[int] = []
        self.stats_calls = 0
        self.refresh_calls: list[tuple[list[str] | None, bool]] = []

    async def stats(self) -> dict[str, int]:
        self.stats_calls += 1
        return {
            "total_notes": 10,
            "orphans": 2,
            "links_in_graph": 8,
            "nodes_in_graph": 10,
        }

    async def neighbors(
        self,
        stem: str,
        *,
        direction: str = "both",
        hops: int = 1,
        limit: int = 50,
    ) -> list[types.SimpleNamespace]:
        self.neighbors_calls.append((stem, direction, hops, limit))
        return [
            types.SimpleNamespace(stem="in-1", title="In 1", path="in-1.md", direction="incoming"),
            types.SimpleNamespace(
                stem="out-1", title="Out 1", path="out-1.md", direction="outgoing"
            ),
            types.SimpleNamespace(
                stem="both-1", title="Both 1", path="both-1.md", direction="both"
            ),
        ]

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[types.SimpleNamespace]:
        self.related_calls.append((stem, max_distance, limit))
        return [
            types.SimpleNamespace(stem="r-1", title="Related 1", path="r-1.md"),
            types.SimpleNamespace(stem="r-2", title="Related 2", path="r-2.md"),
        ]

    async def toc(self, limit: int = 1000) -> list[dict[str, object]]:
        self.toc_calls.append(limit)
        return [
            {
                "id": "n-1",
                "title": "Note 1",
                "path": "notes/n-1.md",
                "tags": ["tag"],
                "lead": "lead",
            },
            {"id": "n-2", "title": "Note 2", "path": "notes/n-2.md", "tags": [], "lead": ""},
        ]

    async def refresh_with_delta(
        self,
        changed_paths: list[str] | None = None,
        *,
        force_full: bool = False,
    ) -> dict[str, object]:
        self.refresh_calls.append((changed_paths, force_full))
        return {
            "mode": "full" if force_full else "delta",
            "changed_count": len(changed_paths or []),
            "force_full": bool(force_full),
            "fallback": False,
        }


def _install_link_graph(monkeypatch: pytest.MonkeyPatch, backend: _FakeBackend) -> None:
    module = types.ModuleType("omni.rag.link_graph")
    module.get_link_graph_backend = lambda notebook_dir=None: backend
    module.LinkGraphDirection = _FakeDirection

    def _normalize(direction: str):
        raw = str(direction or "both").strip().lower()
        if raw in {"to", "incoming"}:
            return _FakeDirection.INCOMING
        if raw in {"from", "outgoing"}:
            return _FakeDirection.OUTGOING
        return _FakeDirection.BOTH

    def _rows(neighbors):
        incoming = []
        outgoing = []
        for n in neighbors:
            direction = str(getattr(n, "direction", "")).lower()
            row = {
                "id": str(getattr(n, "stem", "") or ""),
                "title": str(getattr(n, "title", "") or ""),
                "path": str(getattr(n, "path", "") or ""),
            }
            if direction in {"incoming", "both"}:
                incoming.append({**row, "type": "incoming"})
            if direction in {"outgoing", "both"}:
                outgoing.append({**row, "type": "outgoing"})
        return outgoing, incoming

    module.normalize_link_graph_direction = _normalize
    module.neighbors_to_link_rows = _rows
    monkeypatch.setitem(sys.modules, "omni.rag.link_graph", module)


def _unwrap_skill_command_output(payload: object) -> dict:
    if isinstance(payload, dict) and "content" in payload:
        content = payload.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                import json

                return json.loads(first["text"])
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"unexpected payload type: {type(payload)}")


@pytest.mark.asyncio
async def test_link_graph_stats_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(await link_graph_search.link_graph_stats(paths=paths))

    assert out["success"] is True
    assert out["stats"]["total_notes"] == 10
    assert backend.stats_calls == 1


@pytest.mark.asyncio
async def test_link_graph_stats_no_skill_local_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    _unwrap_skill_command_output(await link_graph_search.link_graph_stats(paths=paths))
    _unwrap_skill_command_output(await link_graph_search.link_graph_stats(paths=paths))
    assert backend.stats_calls == 2


@pytest.mark.asyncio
async def test_link_graph_stats_resource_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)

    class _FakePaths:
        project_root = "."

    monkeypatch.setattr(link_graph_search, "ConfigPaths", _FakePaths)

    out = _unwrap_skill_command_output(await link_graph_search.link_graph_stats_resource())
    assert out["total_notes"] == 10
    assert backend.stats_calls == 1


@pytest.mark.asyncio
async def test_link_graph_toc_resource_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)

    class _FakePaths:
        project_root = "."

    monkeypatch.setattr(link_graph_search, "ConfigPaths", _FakePaths)

    out = _unwrap_skill_command_output(await link_graph_search.link_graph_toc_resource())
    assert out["total"] == 2
    assert out["notes"][0]["title"] == "Note 1"
    assert backend.toc_calls == [1000]


@pytest.mark.asyncio
async def test_link_graph_toc_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(await link_graph_search.link_graph_toc(paths=paths, limit=1))
    assert out["success"] is True
    assert out["total"] == 2
    assert out["returned"] == 1
    assert out["notes"][0]["id"] == "n-1"
    assert backend.toc_calls == [1000]


@pytest.mark.asyncio
async def test_link_graph_links_uses_link_graph_neighbors(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(
        await link_graph_search.link_graph_links(
            note_id="architecture", direction="both", paths=paths
        )
    )

    assert out["success"] is True
    assert out["incoming_count"] == 2
    assert out["outgoing_count"] == 2
    assert out["incoming"][0]["type"] == "incoming"
    assert out["outgoing"][0]["type"] == "outgoing"
    assert backend.neighbors_calls == [("architecture", "both", 1, 200)]


@pytest.mark.asyncio
async def test_link_graph_find_related_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(
        await link_graph_search.link_graph_find_related(
            note_id="architecture",
            max_distance=3,
            limit=7,
            paths=paths,
        )
    )

    assert out["success"] is True
    assert out["total"] == 2
    assert out["results"][0]["id"] == "r-1"
    assert backend.related_calls == [("architecture", 3, 7)]


@pytest.mark.asyncio
async def test_link_graph_refresh_index_calls_common_backend_delta(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(
        await link_graph_search.link_graph_refresh_index(
            changed_paths=["docs/a.md", "assets/knowledge/note.md"],
            force_full=False,
            paths=paths,
        )
    )

    assert out["success"] is True
    assert out["mode"] == "delta"
    assert out["changed_count"] == 2
    assert out["force_full"] is False
    assert backend.refresh_calls == [(["docs/a.md", "assets/knowledge/note.md"], False)]


@pytest.mark.asyncio
async def test_link_graph_refresh_index_calls_common_backend_full(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    backend = _FakeBackend()
    _install_link_graph(monkeypatch, backend)
    paths = types.SimpleNamespace(project_root=tmp_path)

    out = _unwrap_skill_command_output(
        await link_graph_search.link_graph_refresh_index(
            changed_paths=[],
            force_full=True,
            paths=paths,
        )
    )

    assert out["success"] is True
    assert out["mode"] == "full"
    assert out["changed_count"] == 0
    assert out["force_full"] is True
    assert backend.refresh_calls == [([], True)]


@pytest.mark.asyncio
async def test_search_forwards_search_options_to_run_search(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured: dict[str, object] = {}

    async def _fake_run_search(**kwargs):
        captured.update(kwargs)
        return {"success": True, "query": kwargs.get("query", ""), "results": []}

    monkeypatch.setattr(link_graph_search, "_get_run_search", lambda: _fake_run_search)

    paths = types.SimpleNamespace(project_root=tmp_path)
    payload = _unwrap_skill_command_output(
        await link_graph_search.search(
            query="architecture",
            mode="link_graph",
            max_results=5,
            search_options={
                "match_strategy": "exact",
                "sort_terms": [{"field": "title", "order": "asc"}],
                "filters": {"link_to": {"seeds": ["design-doc"]}},
            },
            paths=paths,
        )
    )

    assert payload["success"] is True
    assert captured["query"] == "architecture"
    assert captured["mode"] == "link_graph"
    assert captured["max_results"] == 5
    assert captured["search_options"] == {
        "match_strategy": "exact",
        "sort_terms": [{"field": "title", "order": "asc"}],
        "filters": {"link_to": {"seeds": ["design-doc"]}},
    }
