from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from xiuxian_wendao_py.engine import (
    RustWendaoUnavailableError,
    WendaoEngine,
    _import_engine_class,
    create_engine,
    stats_cache_del,
    stats_cache_get,
    stats_cache_set,
)


class _FakeRustEngine:
    def __init__(self, root: str, *, include_dirs=None, excluded_dirs=None) -> None:
        self.root = root
        self.include_dirs = list(include_dirs or [])
        self.excluded_dirs = list(excluded_dirs or [])
        self.delta_calls: list[tuple[str | None, bool]] = []
        self.refresh_calls = 0

    def search_planned(self, query: str, limit: int, options_json: str) -> str:
        return '{"query":"' + query + '","limit":' + str(limit) + ',"options":' + options_json + "}"

    def related(self, seed: str, max_distance: int, limit: int):
        return [
            {
                "seed": seed,
                "max_distance": max_distance,
                "limit": limit,
            }
        ]

    def neighbors(self, stem: str, direction: str, hops: int, limit: int):
        return (
            '[{"stem":"'
            + stem
            + '","direction":"'
            + direction
            + '","hops":'
            + str(hops)
            + ',"limit":'
            + str(limit)
            + "}]"
        )

    def metadata(self, stem: str):
        return {"stem": stem, "tags": ["t"]}

    def stats(self):
        return '{"total_notes":3,"orphans":1}'

    def cache_schema_info(self):
        return {
            "backend": "valkey",
            "cache_status": "hit",
            "cache_miss_reason": "",
            "schema_version": "omni.link_graph.valkey_cache_snapshot.v1",
            "schema_fingerprint": "abc123",
        }

    def toc(self, limit: int):
        return [{"stem": "a", "limit": limit}]

    def refresh(self):
        self.refresh_calls += 1

    def refresh_with_delta(self, payload: str | None, force_full: bool):
        self.delta_calls.append((payload, force_full))

    def refresh_plan_apply(
        self,
        payload: str | None,
        force_full: bool,
        full_rebuild_threshold: int | None,
    ):
        changed_paths = [] if payload is None else [p for p in json.loads(payload) if p]
        strategy = "full" if force_full else ("noop" if not changed_paths else "delta")
        return {
            "mode": strategy,
            "changed_count": len(changed_paths),
            "force_full": bool(force_full),
            "fallback": False,
            "events": [
                {
                    "phase": "link_graph.index.delta.plan",
                    "duration_ms": 0.0,
                    "extra": {
                        "strategy": strategy,
                        "threshold": full_rebuild_threshold,
                    },
                }
            ],
        }


def test_import_engine_class_missing_module(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_name: str):
        raise ImportError("missing")

    monkeypatch.setattr("importlib.import_module", _raise)

    with pytest.raises(RustWendaoUnavailableError):
        _import_engine_class()


def test_import_engine_class_missing_binding_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "importlib.import_module",
        lambda _name: SimpleNamespace(),
    )

    with pytest.raises(RustWendaoUnavailableError, match="PyLinkGraphEngine"):
        _import_engine_class()


def test_create_engine_and_core_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "xiuxian_wendao_py.engine._import_engine_class",
        lambda: _FakeRustEngine,
    )

    engine = create_engine(
        root="~/notes",
        include_dirs=["docs"],
        excluded_dirs=["target"],
    )

    assert isinstance(engine, WendaoEngine)
    assert engine.raw.include_dirs == ["docs"]
    assert engine.raw.excluded_dirs == ["target"]

    planned = engine.search_planned("q", limit=7, options={"match_strategy": "fts"})
    assert planned["query"] == "q"
    assert planned["limit"] == 7
    assert planned["options"]["match_strategy"] == "fts"

    related = engine.related("a", max_distance=3, limit=9)
    assert related[0]["seed"] == "a"
    assert related[0]["max_distance"] == 3
    assert related[0]["limit"] == 9

    neighbors = engine.neighbors("s", direction="both", hops=2, limit=5)
    assert neighbors[0]["stem"] == "s"
    assert neighbors[0]["direction"] == "both"
    assert neighbors[0]["hops"] == 2
    assert neighbors[0]["limit"] == 5

    metadata = engine.metadata("s")
    assert metadata["stem"] == "s"
    assert metadata["tags"] == ["t"]

    stats = engine.stats()
    assert stats["total_notes"] == 3
    assert stats["orphans"] == 1

    schema_info = engine.cache_schema_info()
    assert schema_info["backend"] == "valkey"
    assert schema_info["cache_status"] == "hit"
    assert schema_info["cache_miss_reason"] == ""
    assert schema_info["schema_version"] == "omni.link_graph.valkey_cache_snapshot.v1"
    assert schema_info["schema_fingerprint"] == "abc123"

    toc = engine.toc(limit=11)
    assert toc[0]["stem"] == "a"
    assert toc[0]["limit"] == 11


def test_refresh_prefers_refresh_with_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DeltaOnlyEngine(_FakeRustEngine):
        refresh = None  # type: ignore[assignment]

    monkeypatch.setattr(
        "xiuxian_wendao_py.engine._import_engine_class",
        lambda: _DeltaOnlyEngine,
    )
    engine = create_engine(root=".")
    engine.refresh()
    assert engine.raw.delta_calls == [(None, True)]


def test_refresh_with_delta_encodes_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "xiuxian_wendao_py.engine._import_engine_class",
        lambda: _FakeRustEngine,
    )
    engine = create_engine(root=".")
    engine.refresh_with_delta(["docs/a.md", "", "docs/b.md"], force_full=False)
    assert engine.raw.delta_calls == [('["docs/a.md", "docs/b.md"]', False)]


def test_refresh_plan_apply_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "xiuxian_wendao_py.engine._import_engine_class",
        lambda: _FakeRustEngine,
    )
    engine = create_engine(root=".")
    payload = engine.refresh_plan_apply(
        ["docs/a.md", "", "docs/b.md"],
        force_full=False,
        full_rebuild_threshold=5,
    )
    assert payload["mode"] == "delta"
    assert payload["changed_count"] == 2
    assert payload["events"][0]["extra"]["threshold"] == 5


def test_stats_cache_helpers_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, str] = {}

    def _get(source_key: str, _ttl: float):
        return state.get(source_key)

    def _set(source_key: str, stats_json: str, _ttl: float):
        state[source_key] = (
            '{"schema":"omni.link_graph.stats.cache.v1","source_key":"'
            + source_key
            + '","updated_at_unix":1739980800.0,"stats":'
            + stats_json
            + "}"
        )

    def _del(source_key: str):
        state.pop(source_key, None)

    monkeypatch.setattr(
        "importlib.import_module",
        lambda _name: SimpleNamespace(
            PyLinkGraphEngine=_FakeRustEngine,
            link_graph_stats_cache_get=_get,
            link_graph_stats_cache_set=_set,
            link_graph_stats_cache_del=_del,
        ),
    )

    assert stats_cache_get("k", 300.0) is None
    stats_cache_set(
        "k",
        {"stats": {"total_notes": 3, "orphans": 1, "links_in_graph": 4, "nodes_in_graph": 3}},
        300.0,
    )
    payload = stats_cache_get("k", 300.0)
    assert payload is not None
    assert payload["schema"] == "omni.link_graph.stats.cache.v1"
    assert payload["source_key"] == "k"
    stats_cache_del("k")
    assert stats_cache_get("k", 300.0) is None
