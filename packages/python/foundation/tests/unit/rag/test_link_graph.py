"""Tests for common link-graph engine contracts and adapters."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import pytest

from omni.rag.link_graph import (
    LinkGraphDirection,
    LinkGraphMetadata,
    LinkGraphNeighbor,
    LinkGraphSearchOptions,
    WendaoLinkGraphBackend,
    apply_link_graph_proximity_boost,
)


@pytest.fixture(autouse=True)
def _default_link_graph_cache_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.delenv("REDIS_URL", raising=False)


class _FakeGraphBackend:
    backend_name = "wendao"

    async def search_planned(self, query: str, limit: int = 20, options=None) -> dict[str, object]:
        del options
        return {"query": query, "search_options": {}, "hits": []}

    async def neighbors(
        self,
        stem: str,
        *,
        direction: LinkGraphDirection = LinkGraphDirection.BOTH,
        hops: int = 1,
        limit: int = 50,
    ) -> list[LinkGraphNeighbor]:
        del direction, hops, limit
        if stem == "a":
            return [
                LinkGraphNeighbor(
                    stem="b",
                    direction=LinkGraphDirection.BOTH,
                    distance=1,
                    title="B",
                    path="docs/b.md",
                )
            ]
        if stem == "b":
            return [
                LinkGraphNeighbor(
                    stem="a",
                    direction=LinkGraphDirection.BOTH,
                    distance=1,
                    title="A",
                    path="docs/a.md",
                )
            ]
        return []

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[LinkGraphNeighbor]:
        del stem, max_distance, limit
        return []

    async def metadata(self, stem: str) -> LinkGraphMetadata | None:
        if stem in {"a", "b"}:
            return LinkGraphMetadata(
                stem=stem,
                tags=["tag-x"],
                title=stem.upper(),
                path=f"docs/{stem}.md",
            )
        return None

    async def toc(self, limit: int = 1000) -> list[dict[str, object]]:
        rows = [
            {"id": "a", "title": "A", "tags": ["tag-x"], "lead": "a", "path": "docs/a.md"},
            {"id": "b", "title": "B", "tags": [], "lead": "b", "path": "docs/b.md"},
        ]
        return rows[: max(1, int(limit))]

    async def stats(self) -> dict[str, int]:
        return {"total_notes": 2, "orphans": 0, "links_in_graph": 1, "nodes_in_graph": 2}

    async def create_note(
        self,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> object | None:
        del title, body, tags
        return None


class _SlowLinkGraphBackend:
    backend_name = "wendao"

    def __init__(self) -> None:
        self.neighbor_calls = 0
        self.metadata_calls = 0

    async def search_planned(self, query: str, limit: int = 20, options=None) -> dict[str, object]:
        del options
        return {"query": query, "search_options": {}, "hits": []}

    async def neighbors(
        self,
        stem: str,
        *,
        direction: LinkGraphDirection = LinkGraphDirection.BOTH,
        hops: int = 1,
        limit: int = 50,
    ) -> list[LinkGraphNeighbor]:
        del stem, direction, hops, limit
        self.neighbor_calls += 1
        await asyncio.sleep(0.1)
        return []

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[LinkGraphNeighbor]:
        del stem, max_distance, limit
        return []

    async def metadata(self, stem: str) -> LinkGraphMetadata | None:
        del stem
        self.metadata_calls += 1
        await asyncio.sleep(0.1)
        return None

    async def toc(self, limit: int = 1000) -> list[dict[str, object]]:
        del limit
        return []

    async def stats(self) -> dict[str, int]:
        return {"total_notes": 0, "orphans": 0, "links_in_graph": 0, "nodes_in_graph": 0}

    async def create_note(
        self,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> object | None:
        del title, body, tags
        return None


class _FakeWendaoEngine:
    def __init__(self) -> None:
        self.search_planned_calls: list[tuple[str, int, str]] = []
        self.refresh_calls: list[tuple[str | None, bool]] = []
        self.fail_delta_refresh = False

    @staticmethod
    def _results_payload() -> list[dict[str, object]]:
        return [
            {
                "stem": "note-a",
                "title": "Note A",
                "path": "docs/note-a.md",
                "score": 0.91,
                "best_section": "Architecture / Recall",
                "match_reason": "path_fuzzy+section_heading_contains",
            },
            {"stem": "note-b", "title": "Note B", "path": "docs/note-b.md", "score": 0.55},
        ]

    def neighbors(self, stem: str, direction: str, hops: int, limit: int) -> str:
        del stem, direction, hops, limit
        return json.dumps(
            [
                {
                    "stem": "note-b",
                    "title": "Note B",
                    "path": "docs/note-b.md",
                    "distance": 1,
                    "direction": "outgoing",
                }
            ]
        )

    def related(self, stem: str, max_distance: int, limit: int) -> str:
        del stem, max_distance, limit
        return json.dumps(
            [
                {
                    "stem": "note-c",
                    "title": "Note C",
                    "path": "docs/note-c.md",
                    "distance": 2,
                }
            ]
        )

    def metadata(self, stem: str) -> str:
        del stem
        return json.dumps(
            {
                "stem": "note-a",
                "title": "Note A",
                "path": "docs/note-a.md",
                "tags": ["tag-x", "tag-y"],
            }
        )

    def search_planned(self, query: str, limit: int, options_json: str) -> str:
        self.search_planned_calls.append((query, limit, options_json))
        return json.dumps(
            {
                "query": query,
                "options": json.loads(options_json),
                "results": self._results_payload(),
            }
        )

    def toc(self, limit: int) -> str:
        del limit
        return json.dumps(
            [
                {
                    "id": "note-a",
                    "stem": "note-a",
                    "title": "Note A",
                    "path": "docs/note-a.md",
                    "tags": ["tag-x"],
                    "lead": "lead a",
                },
                {
                    "id": "note-b",
                    "stem": "note-b",
                    "title": "Note B",
                    "path": "docs/note-b.md",
                    "tags": [],
                    "lead": "lead b",
                },
            ]
        )

    def stats(self) -> str:
        return json.dumps(
            {
                "total_notes": 2,
                "orphans": 1,
                "links_in_graph": 1,
                "nodes_in_graph": 2,
            }
        )

    def refresh_with_delta(self, changed_paths_json: str | None, force_full: bool) -> None:
        self.refresh_calls.append((changed_paths_json, force_full))
        if self.fail_delta_refresh and not force_full:
            raise ValueError("delta refresh failed")
        return None

    def refresh_plan_apply(
        self,
        changed_paths_json: str | None,
        force_full: bool,
        full_rebuild_threshold: int | None,
    ) -> str:
        changed_paths = json.loads(changed_paths_json or "[]")
        threshold = max(1, int(full_rebuild_threshold or 256))
        changed_count = len(changed_paths)
        strategy = (
            "full"
            if force_full or changed_count >= threshold
            else ("noop" if not changed_paths else "delta")
        )
        reason = (
            "force_full"
            if force_full
            else (
                "threshold_exceeded"
                if changed_count >= threshold
                else ("noop" if not changed_paths else "delta_requested")
            )
        )
        events = [
            {
                "phase": "link_graph.index.delta.plan",
                "duration_ms": 0.0,
                "extra": {
                    "strategy": strategy,
                    "reason": reason,
                    "changed_count": changed_count,
                    "force_full": bool(force_full),
                    "threshold": threshold,
                    "delta_supported": True,
                    "full_refresh_supported": True,
                },
            }
        ]
        if strategy == "noop":
            return json.dumps(
                {
                    "mode": "noop",
                    "changed_count": 0,
                    "force_full": False,
                    "fallback": False,
                    "events": events,
                }
            )
        if strategy == "full":
            self.refresh_calls.append((None, True))
            events.append(
                {
                    "phase": "link_graph.index.rebuild.full",
                    "duration_ms": 0.0,
                    "extra": {
                        "success": True,
                        "reason": reason,
                        "changed_count": changed_count,
                    },
                }
            )
            return json.dumps(
                {
                    "mode": "full",
                    "changed_count": changed_count,
                    "force_full": bool(force_full),
                    "fallback": False,
                    "events": events,
                }
            )

        self.refresh_calls.append((changed_paths_json, False))
        if self.fail_delta_refresh:
            events.append(
                {
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": 0.0,
                    "extra": {
                        "success": False,
                        "changed_count": changed_count,
                        "error": "delta refresh failed",
                    },
                }
            )
            self.refresh_calls.append((None, True))
            events.append(
                {
                    "phase": "link_graph.index.rebuild.full",
                    "duration_ms": 0.0,
                    "extra": {
                        "success": True,
                        "reason": "delta_failed_fallback",
                        "changed_count": changed_count,
                    },
                }
            )
            return json.dumps(
                {
                    "mode": "full",
                    "changed_count": changed_count,
                    "force_full": False,
                    "fallback": True,
                    "events": events,
                }
            )

        events.append(
            {
                "phase": "link_graph.index.delta.apply",
                "duration_ms": 0.0,
                "extra": {
                    "success": True,
                    "changed_count": changed_count,
                },
            }
        )
        return json.dumps(
            {
                "mode": "delta",
                "changed_count": changed_count,
                "force_full": False,
                "fallback": False,
                "events": events,
            }
        )


@pytest.mark.asyncio
async def test_fake_graph_backend_neighbors_returns_linked_note() -> None:
    backend = _FakeGraphBackend()
    neighbors = await backend.neighbors("a", direction=LinkGraphDirection.BOTH, hops=1, limit=10)
    assert len(neighbors) == 1
    n = neighbors[0]
    assert n.stem == "b"
    assert n.direction == LinkGraphDirection.BOTH


@pytest.mark.asyncio
async def test_fake_graph_backend_metadata_returns_tags() -> None:
    backend = _FakeGraphBackend()
    meta = await backend.metadata("a")
    assert isinstance(meta, LinkGraphMetadata)
    assert meta is not None
    assert meta.stem == "a"
    assert meta.tags == ["tag-x"]


@pytest.mark.asyncio
async def test_fake_graph_backend_toc_returns_rows() -> None:
    backend = _FakeGraphBackend()
    toc = await backend.toc(limit=10)
    assert len(toc) == 2
    assert toc[0]["id"] == "a"
    assert toc[0]["title"] == "A"
    assert toc[0]["path"] == "docs/a.md"


@pytest.mark.asyncio
async def test_apply_link_graph_proximity_boost_boosts_linked_and_tagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omni.rag.link_graph import proximity as proximity_module

    backend = _FakeGraphBackend()
    monkeypatch.setitem(sys.modules, "omni_core_rs", None)
    proximity_module._stem_cache.clear()

    rows = [
        {"source": "docs/a.md", "score": 0.8, "content": "A"},
        {"source": "docs/b.md", "score": 0.6, "content": "B"},
        {"source": "docs/c.md", "score": 0.5, "content": "C"},
    ]

    out = await apply_link_graph_proximity_boost(
        rows,
        "query",
        backend=backend,
        notebook_dir="test_link_graph_boost",
    )
    by_source = {row["source"]: row["score"] for row in out}
    expected_boost = (
        proximity_module.DEFAULT_LINK_PROXIMITY_BOOST + proximity_module.DEFAULT_TAG_PROXIMITY_BOOST
    )
    assert by_source["docs/a.md"] == pytest.approx(0.8 + expected_boost, abs=0.001)
    assert by_source["docs/b.md"] == pytest.approx(0.6 + expected_boost, abs=0.001)
    assert by_source["docs/c.md"] == pytest.approx(0.5, abs=0.001)


@pytest.mark.asyncio
async def test_apply_link_graph_proximity_boost_passthrough_for_single_result() -> None:
    backend = _FakeGraphBackend()
    rows = [{"source": "docs/a.md", "score": 0.8, "content": "A"}]
    out = await apply_link_graph_proximity_boost(rows, "query", backend=backend)
    assert out == rows


@pytest.mark.asyncio
async def test_apply_link_graph_proximity_boost_respects_timeout_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omni.rag.link_graph import proximity as proximity_module

    rows = [
        {"source": "docs/a.md", "score": 0.8, "content": "A"},
        {"source": "docs/b.md", "score": 0.6, "content": "B"},
    ]

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.proximity.timeout_seconds": 0.01,
            "link_graph.proximity.max_parallel_stems": 1,
            "link_graph.proximity.stem_cache_ttl_seconds": 0,
        }
        return values.get(key, default)

    backend = _SlowLinkGraphBackend()
    monkeypatch.setattr(proximity_module, "get_setting", _fake_get_setting)
    out = await apply_link_graph_proximity_boost(rows, "query", backend=backend)
    assert [row["source"] for row in out] == ["docs/a.md", "docs/b.md"]
    assert [row["score"] for row in out] == [0.8, 0.6]
    assert backend.neighbor_calls >= 1


@pytest.mark.asyncio
async def test_apply_link_graph_proximity_boost_skips_after_recent_policy_timeout() -> None:
    from omni.rag.link_graph import policy as policy_module

    rows = [
        {"source": "docs/a.md", "score": 0.8, "content": "A"},
        {"source": "docs/b.md", "score": 0.6, "content": "B"},
    ]

    backend = _SlowLinkGraphBackend()
    policy_module.note_recent_graph_search_timeout("query-timeout")
    out = await apply_link_graph_proximity_boost(rows, "query-timeout", backend=backend)

    assert [row["source"] for row in out] == ["docs/a.md", "docs/b.md"]
    assert [row["score"] for row in out] == [0.8, 0.6]
    assert backend.neighbor_calls == 0
    assert backend.metadata_calls == 0
    assert policy_module.take_recent_graph_search_timeout("query-timeout") is False


def test_neighbor_to_record_uses_schema_shape() -> None:
    row = LinkGraphNeighbor(stem="b", direction=LinkGraphDirection.OUTGOING, distance=2).to_record()
    assert row["schema"] == "omni.link_graph.record.v1"
    assert row["kind"] == "neighbor"
    assert row["distance"] == 2


@pytest.mark.asyncio
async def test_fake_graph_backend_stats_are_normalized() -> None:
    backend = _FakeGraphBackend()
    stats = await backend.stats()
    assert stats == {
        "total_notes": 2,
        "orphans": 0,
        "links_in_graph": 1,
        "nodes_in_graph": 2,
    }


@pytest.mark.asyncio
async def test_wendao_backend_stats_requires_rust_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: default)

    backend = WendaoLinkGraphBackend(notebook_dir=str(tmp_path / "notebook"))
    with pytest.raises(RuntimeError, match="engine unavailable"):
        await backend.stats()


@pytest.mark.asyncio
async def test_wendao_backend_toc_requires_rust_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: default)

    backend = WendaoLinkGraphBackend(notebook_dir=str(tmp_path / "notebook"))
    with pytest.raises(RuntimeError, match="engine unavailable"):
        await backend.toc(limit=10)


@pytest.mark.asyncio
async def test_wendao_backend_create_note_is_read_only(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    backend = WendaoLinkGraphBackend(notebook_dir=str(tmp_path / "notebook"))
    created = await backend.create_note("x", "y", tags=["t"])
    assert created is None


@pytest.mark.asyncio
async def test_wendao_backend_core_methods_use_rust_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    fake_engine = _FakeWendaoEngine()
    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )

    planned = await backend.search_planned("note", limit=2)
    hits = planned["hits"]
    assert [hit.stem for hit in hits] == ["note-a", "note-b"]
    assert hits[0].score == pytest.approx(0.91)
    assert hits[0].best_section == "Architecture / Recall"
    assert hits[0].match_reason == "path_fuzzy+section_heading_contains"
    assert len(fake_engine.search_planned_calls) == 1
    options_payload = json.loads(fake_engine.search_planned_calls[0][2])
    assert options_payload == {
        "match_strategy": "fts",
        "case_sensitive": False,
        "sort_terms": [{"field": "score", "order": "desc"}],
        "filters": {},
    }

    neighbors = await backend.neighbors(
        "note-a", direction=LinkGraphDirection.OUTGOING, hops=1, limit=5
    )
    assert len(neighbors) == 1
    assert neighbors[0].stem == "note-b"
    assert neighbors[0].direction == LinkGraphDirection.OUTGOING

    related = await backend.related("note-a", max_distance=2, limit=5)
    assert len(related) == 1
    assert related[0].stem == "note-c"
    assert related[0].direction == LinkGraphDirection.BOTH

    metadata = await backend.metadata("note-a")
    assert metadata is not None
    assert metadata.stem == "note-a"
    assert metadata.tags == ["tag-x", "tag-y"]


@pytest.mark.asyncio
async def test_wendao_backend_search_passes_custom_options(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    fake_engine = _FakeWendaoEngine()
    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )

    options = LinkGraphSearchOptions.from_dict(
        {
            "match_strategy": "exact",
            "case_sensitive": True,
            "sort_terms": [{"field": "title", "order": "asc"}],
            "filters": {
                "link_to": {"seeds": ["architecture"]},
                "linked_by": {"seeds": ["memory"]},
                "related": {
                    "seeds": ["router"],
                    "max_distance": 3,
                    "ppr": {
                        "alpha": 0.9,
                        "max_iter": 64,
                        "tol": 1e-6,
                        "subgraph_mode": "force",
                    },
                },
                "scope": "section_only",
                "max_heading_level": 3,
                "max_tree_hops": 2,
                "collapse_to_doc": False,
                "edge_types": ["structural", "verified"],
                "per_doc_section_cap": 4,
                "min_section_words": 18,
            },
        }
    )
    planned = await backend.search_planned("Note A", limit=2, options=options)
    hits = planned["hits"]

    assert [hit.stem for hit in hits] == ["note-a", "note-b"]
    assert len(fake_engine.search_planned_calls) == 1
    payload = json.loads(fake_engine.search_planned_calls[0][2])
    assert payload == {
        "match_strategy": "exact",
        "case_sensitive": True,
        "sort_terms": [{"field": "title", "order": "asc"}],
        "filters": {
            "link_to": {"seeds": ["architecture"]},
            "linked_by": {"seeds": ["memory"]},
            "related": {
                "seeds": ["router"],
                "max_distance": 3,
                "ppr": {
                    "alpha": 0.9,
                    "max_iter": 64,
                    "tol": 1e-6,
                    "subgraph_mode": "force",
                },
            },
            "scope": "section_only",
            "max_heading_level": 3,
            "max_tree_hops": 2,
            "collapse_to_doc": False,
            "edge_types": ["structural", "verified"],
            "per_doc_section_cap": 4,
            "min_section_words": 18,
        },
    }


@pytest.mark.asyncio
async def test_wendao_backend_search_planned_returns_effective_options(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    fake_engine = _FakeWendaoEngine()

    def _planned(query: str, limit: int, options_json: str) -> str:
        fake_engine.search_planned_calls.append((query, limit, options_json))
        return json.dumps(
            {
                "query": "architecture design",
                "options": {
                    "match_strategy": "exact",
                    "case_sensitive": False,
                    "sort_terms": [{"field": "path", "order": "asc"}],
                    "filters": {"tags": {"any": ["architecture", "design"], "not": ["draft"]}},
                },
                "results": fake_engine._results_payload(),
            }
        )

    monkeypatch.setattr(fake_engine, "search_planned", _planned)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )
    planned = await backend.search_planned(
        "tag:(architecture OR design) -tag:draft sort:path_asc",
        limit=2,
    )

    assert planned["query"] == "architecture design"
    assert planned["search_options"] == {
        "match_strategy": "exact",
        "case_sensitive": False,
        "sort_terms": [{"field": "path", "order": "asc"}],
        "filters": {"tags": {"any": ["architecture", "design"], "not": ["draft"]}},
    }
    assert [hit.stem for hit in planned["hits"]] == ["note-a", "note-b"]
    assert len(fake_engine.search_planned_calls) == 1


@pytest.mark.asyncio
async def test_wendao_backend_search_planned_records_monitor_phase(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    fake_engine = _FakeWendaoEngine()
    captured: list[tuple[str, float, dict[str, object]]] = []

    def _fake_record_phase(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    monkeypatch.setattr("omni.foundation.runtime.skills_monitor.record_phase", _fake_record_phase)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )
    planned = await backend.search_planned("architecture", limit=2)

    assert planned["query"] == "architecture"
    search_phase = next((row for row in captured if row[0] == "link_graph.search_planned"), None)
    assert search_phase is not None
    _, duration_ms, extra = search_phase
    assert float(duration_ms) >= 0.0
    assert extra["success"] is True
    assert int(extra["limit"]) == 2
    assert int(extra["hit_count"]) == 2
    assert str(extra["match_strategy"]) == "fts"
    phase_names = [row[0] for row in captured]
    assert "link_graph.search.rank_fusion" in phase_names


@pytest.mark.asyncio
async def test_wendao_backend_refresh_with_delta_records_phases(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: default)
    fake_engine = _FakeWendaoEngine()
    captured: list[tuple[str, float, dict[str, object]]] = []

    def _fake_record_phase(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    monkeypatch.setattr("omni.foundation.runtime.skills_monitor.record_phase", _fake_record_phase)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )
    result = await backend.refresh_with_delta(["docs/a.md"])

    assert result["mode"] == "delta"
    assert len(fake_engine.refresh_calls) == 1
    delta_payload, delta_force_full = fake_engine.refresh_calls[0]
    assert delta_force_full is False
    assert isinstance(delta_payload, str)
    assert json.loads(delta_payload) == ["docs/a.md"]
    phase_names = [row[0] for row in captured]
    assert "link_graph.index.delta.plan" in phase_names
    assert "link_graph.index.delta.apply" in phase_names
    assert "link_graph.index.rebuild.full" not in phase_names


@pytest.mark.asyncio
async def test_wendao_backend_refresh_with_delta_fallbacks_to_full_on_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: default)
    fake_engine = _FakeWendaoEngine()
    fake_engine.fail_delta_refresh = True
    captured: list[tuple[str, float, dict[str, object]]] = []

    def _fake_record_phase(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    monkeypatch.setattr("omni.foundation.runtime.skills_monitor.record_phase", _fake_record_phase)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )
    result = await backend.refresh_with_delta(["docs/a.md"])

    assert result["mode"] == "full"
    assert result["fallback"] is True
    assert len(fake_engine.refresh_calls) == 2
    assert fake_engine.refresh_calls[0][1] is False
    assert fake_engine.refresh_calls[1] == (None, True)

    delta_apply = [row for row in captured if row[0] == "link_graph.index.delta.apply"]
    assert delta_apply
    assert bool(delta_apply[0][2]["success"]) is False
    full_rebuild = [row for row in captured if row[0] == "link_graph.index.rebuild.full"]
    assert full_rebuild
    assert bool(full_rebuild[0][2]["success"]) is True


@pytest.mark.asyncio
async def test_wendao_backend_refresh_with_delta_falls_back_to_refresh_when_delta_api_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: default)
    captured: list[tuple[str, float, dict[str, object]]] = []

    class _RefreshOnlyEngine:
        def __init__(self) -> None:
            self.refresh_calls = 0

        def refresh(self) -> None:
            self.refresh_calls += 1

    engine = _RefreshOnlyEngine()

    def _fake_record_phase(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    monkeypatch.setattr("omni.foundation.runtime.skills_monitor.record_phase", _fake_record_phase)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=engine,
    )
    result = await backend.refresh_with_delta(["docs/a.md"])

    assert result["mode"] == "full"
    assert result["fallback"] is False
    assert engine.refresh_calls == 1

    plan_events = [row for row in captured if row[0] == "link_graph.index.delta.plan"]
    assert plan_events
    assert str(plan_events[0][2].get("reason")) == "engine_delta_unavailable"
    assert bool(plan_events[0][2].get("delta_supported")) is False
    full_rebuild = [row for row in captured if row[0] == "link_graph.index.rebuild.full"]
    assert full_rebuild
    assert bool(full_rebuild[0][2]["success"]) is True


@pytest.mark.asyncio
async def test_wendao_backend_refresh_with_delta_respects_full_rebuild_threshold(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    def _fake_get_setting(key: str, default=None):
        if key == "link_graph.index.delta.full_rebuild_threshold":
            return 1
        return default

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    fake_engine = _FakeWendaoEngine()
    captured: list[tuple[str, float, dict[str, object]]] = []

    def _fake_record_phase(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    monkeypatch.setattr("omni.foundation.runtime.skills_monitor.record_phase", _fake_record_phase)

    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=fake_engine,
    )
    result = await backend.refresh_with_delta(["docs/a.md"])

    assert result["mode"] == "full"
    assert result["fallback"] is False
    assert fake_engine.refresh_calls == [(None, True)]

    plan_events = [row for row in captured if row[0] == "link_graph.index.delta.plan"]
    assert plan_events
    assert str(plan_events[0][2].get("strategy")) == "full"
    assert str(plan_events[0][2].get("reason")) == "threshold_exceeded"
    assert int(plan_events[0][2].get("threshold", 0)) == 1


@pytest.mark.asyncio
async def test_wendao_backend_search_rejects_invalid_options(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=_FakeWendaoEngine(),
    )

    with pytest.raises(ValueError, match="match_strategy"):
        await backend.search_planned(
            "note",
            limit=2,
            options={"match_strategy": "bm25"},
        )


@pytest.mark.asyncio
async def test_wendao_backend_search_rejects_invalid_max_distance(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=_FakeWendaoEngine(),
    )

    with pytest.raises(ValueError, match="max_distance"):
        await backend.search_planned(
            "note",
            limit=2,
            options={"filters": {"related": {"seeds": ["note"], "max_distance": 0}}},
        )


@pytest.mark.asyncio
async def test_wendao_backend_toc_stats_prefer_rust_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)
    backend = WendaoLinkGraphBackend(
        notebook_dir=str(tmp_path / "notebook"),
        engine=_FakeWendaoEngine(),
    )

    toc = await backend.toc(limit=5)
    assert len(toc) == 2
    assert toc[0]["id"] == "note-a"
    assert toc[0]["path"] == "docs/note-a.md"

    stats = await backend.stats()
    assert stats == {
        "total_notes": 2,
        "orphans": 1,
        "links_in_graph": 1,
        "nodes_in_graph": 2,
    }


@pytest.mark.asyncio
async def test_wendao_backend_search_lazy_initializes_engine_once(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()
    monkeypatch.setattr(wendao_backend_module, "get_setting", lambda key, default=None: False)

    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    calls = {"count": 0}
    fake_engine = _FakeWendaoEngine()

    def _fake_init_engine():
        calls["count"] += 1
        return fake_engine

    monkeypatch.setattr(backend, "_init_engine", _fake_init_engine)

    first = await backend.search_planned("note", limit=1)
    second = await backend.search_planned("note", limit=1)
    assert [hit.stem for hit in first["hits"]] == ["note-a"]
    assert [hit.stem for hit in second["hits"]] == ["note-a"]
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_wendao_backend_stats_uses_persistent_cache_without_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.stats_persistent_cache_ttl_sec": 300.0,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    backend._stats_cache_getter = lambda _source, _ttl: {
        "schema": "omni.link_graph.stats.cache.v1",
        "source_key": backend._source_key(),
        "updated_at_unix": time.time(),
        "stats": {
            "total_notes": 9,
            "orphans": 4,
            "links_in_graph": 11,
            "nodes_in_graph": 9,
        },
    }

    def _fail_init_engine():
        raise AssertionError("engine init should not run when persistent cache is valid")

    monkeypatch.setattr(backend, "_init_engine", _fail_init_engine)
    stats = await backend.stats()
    assert stats == {
        "total_notes": 9,
        "orphans": 4,
        "links_in_graph": 11,
        "nodes_in_graph": 9,
    }


@pytest.mark.asyncio
async def test_wendao_backend_stats_persists_cache_after_engine_read(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.stats_persistent_cache_ttl_sec": 300.0,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    captured: dict[str, object] = {}
    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook), engine=_FakeWendaoEngine())
    backend._stats_cache_setter = lambda source_key, payload, ttl_sec: captured.update(
        {
            "source_key": source_key,
            "payload": dict(payload),
            "ttl_sec": ttl_sec,
        }
    )

    stats = await backend.stats()
    payload = captured.get("payload")
    assert isinstance(payload, dict)
    assert payload["schema"] == "omni.link_graph.stats.cache.v1"
    assert payload["source_key"] == backend._source_key()
    assert payload["stats"] == stats
    assert captured["ttl_sec"] == 300.0


def test_wendao_backend_source_key_includes_filters(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs": ["docs/", r"assets\knowledge", "docs"],
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    source_key = backend._source_key()

    assert "include=docs,assets/knowledge" in source_key
    assert "exclude=.git,.cache,.devenv,.run,.venv,target,node_modules" in source_key


def test_wendao_backend_auto_include_dirs_from_candidates(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()
    (notebook / "docs").mkdir()
    (notebook / ".data" / "harvested").mkdir(parents=True)

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs": [],
            "link_graph.include_dirs_auto": True,
            "link_graph.include_dirs_auto_candidates": [
                "docs",
                ".data/harvested",
                "missing",
            ],
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    source_key = backend._source_key()
    assert "include=docs,.data/harvested" in source_key
    assert "missing" not in source_key


def test_wendao_backend_exclude_dirs_additional_only_and_ignores_hidden(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [".cache", "custom-build", "TARGET", "custom-build"],
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    backend = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    source_key = backend._source_key()

    excludes = source_key.split("|exclude=", 1)[1].split(",")
    assert ".git" in excludes
    assert ".cache" in excludes
    assert ".devenv" in excludes
    assert ".run" in excludes
    assert ".venv" in excludes
    assert "custom-build" in excludes
    assert "target" in excludes
    assert excludes.count(".cache") == 1


def test_wendao_backend_stats_cache_slot_changes_with_filter_set(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    state = {"include_dirs": ["docs"]}

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": state["include_dirs"],
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)

    backend_docs = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    slot_docs = backend_docs._resolve_stats_cache_slot_key()

    state["include_dirs"] = ["assets/knowledge"]
    backend_assets = WendaoLinkGraphBackend(notebook_dir=str(notebook))
    slot_assets = backend_assets._resolve_stats_cache_slot_key()

    assert slot_docs != slot_assets


def test_wendao_backend_configures_rust_cache_env_from_link_graph_settings(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [],
            "link_graph.cache.key_prefix": "omni:test:link_graph",
            "link_graph.cache.ttl_seconds": 45,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6380/0")
    monkeypatch.delenv("OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX", raising=False)
    monkeypatch.delenv("OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS", raising=False)

    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert os.environ.get("VALKEY_URL") == "redis://127.0.0.1:6380/0"
    assert os.environ.get("OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX") == "omni:test:link_graph"
    assert os.environ.get("OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS") == "45"


def test_wendao_backend_prefers_cache_setting_over_env(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [],
            "link_graph.cache.valkey_url": "redis://127.0.0.1:6394/0",
            "link_graph.cache.key_prefix": "omni:from:settings",
            "link_graph.cache.ttl_seconds": 120,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6393/0")
    monkeypatch.setenv("OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX", "omni:from:env")
    monkeypatch.setenv("OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS", "999")

    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert os.environ.get("VALKEY_URL") == "redis://127.0.0.1:6394/0"
    assert os.environ.get("OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX") == "omni:from:env"
    assert os.environ.get("OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS") == "999"


def test_wendao_backend_uses_valkey_url_fallback_for_rust_cache_env(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [],
            "link_graph.cache.key_prefix": "omni:link_graph:index",
            "link_graph.cache.ttl_seconds": 300,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    monkeypatch.setenv("VALKEY_URL", "redis://127.0.0.1:6391/0")

    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert os.environ.get("VALKEY_URL") == "redis://127.0.0.1:6391/0"


def test_wendao_backend_reloads_settings_when_cache_valkey_missing_first_read(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    url_state = {"reads": 0}

    def _fake_get_setting(key: str, default=None):
        if key == "link_graph.cache.valkey_url":
            url_state["reads"] += 1
            if url_state["reads"] == 1:
                return None
            return "redis://127.0.0.1:6395/0"
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [],
            "link_graph.cache.key_prefix": "omni:link_graph:index",
            "link_graph.cache.ttl_seconds": 300,
        }
        return values.get(key, default)

    reload_called = {"count": 0}

    class _FakeSettings:
        def reload(self) -> None:
            reload_called["count"] += 1

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    monkeypatch.delenv("VALKEY_URL", raising=False)
    monkeypatch.setattr("omni.foundation.config.settings.Settings", _FakeSettings)

    WendaoLinkGraphBackend(notebook_dir=str(notebook))

    assert reload_called["count"] == 1
    assert os.environ.get("VALKEY_URL") == "redis://127.0.0.1:6395/0"


def test_wendao_backend_ignores_redis_url_for_link_graph_cache_env(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import omni.rag.link_graph.wendao_backend as wendao_backend_module

    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _fake_get_setting(key: str, default=None):
        values = {
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs": [],
            "link_graph.exclude_dirs": [],
            "link_graph.cache.key_prefix": "omni:link_graph:index",
            "link_graph.cache.ttl_seconds": 300,
        }
        return values.get(key, default)

    monkeypatch.setattr(wendao_backend_module, "get_setting", _fake_get_setting)
    monkeypatch.delenv("VALKEY_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6392/0")

    with pytest.raises(RuntimeError, match="set VALKEY_URL"):
        WendaoLinkGraphBackend(notebook_dir=str(notebook))
