from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

import pytest

from xiuxian_wendao_py.backend import WendaoBackend
from xiuxian_wendao_py.models import (
    DEFAULT_EXCLUDED_ADDITIONAL_DIRS,
    DEFAULT_EXCLUDED_HIDDEN_DIRS,
    LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION,
    LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION,
    WendaoRuntimeConfig,
)

if TYPE_CHECKING:
    from pathlib import Path


def _runtime_config(
    *,
    cache_valkey_url: str = "redis://127.0.0.1:6379/0",
    stats_ttl: float = 120.0,
) -> WendaoRuntimeConfig:
    return WendaoRuntimeConfig(
        root_dir=None,
        include_dirs=[],
        include_dirs_auto=False,
        include_dirs_auto_candidates=[],
        exclude_dirs=[*DEFAULT_EXCLUDED_HIDDEN_DIRS, *DEFAULT_EXCLUDED_ADDITIONAL_DIRS],
        stats_persistent_cache_ttl_sec=stats_ttl,
        delta_full_rebuild_threshold=256,
        cache_valkey_url=cache_valkey_url,
        cache_key_prefix=None,
        cache_ttl_seconds=None,
    )


class _FakeEngine:
    def __init__(self) -> None:
        self.search_calls: list[tuple[str, int, str]] = []
        self.refresh_calls: list[tuple[str | None, bool]] = []
        self.fail_delta = False

    def search_planned(self, query: str, limit: int, options_json: str) -> str:
        self.search_calls.append((query, limit, options_json))
        return json.dumps(
            {
                "query": query,
                "options": json.loads(options_json),
                "results": [
                    {"stem": "note-a", "score": 0.91, "title": "Note A", "path": "docs/note-a.md"},
                    {"stem": "note-b", "score": 0.55, "title": "Note B", "path": "docs/note-b.md"},
                ],
            }
        )

    def neighbors(self, stem: str, direction: str, hops: int, limit: int) -> str:
        del stem, direction, hops, limit
        return "[]"

    def related(self, stem: str, max_distance: int, limit: int) -> str:
        del stem, max_distance, limit
        return "[]"

    def metadata(self, stem: str) -> str:
        del stem
        return "{}"

    def toc(self, limit: int) -> str:
        del limit
        return "[]"

    def stats(self) -> str:
        return json.dumps(
            {
                "total_notes": 2,
                "orphans": 1,
                "links_in_graph": 1,
                "nodes_in_graph": 2,
            }
        )

    def cache_schema_info(self) -> str:
        return json.dumps(
            {
                "backend": "valkey",
                "cache_status": "hit",
                "cache_miss_reason": "",
                "schema_version": LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION,
                "schema_fingerprint": "cafef00d",
            }
        )

    def refresh_with_delta(self, payload: str | None, force_full: bool) -> None:
        self.refresh_calls.append((payload, force_full))
        if self.fail_delta and not force_full:
            raise ValueError("delta failed")

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
        if self.fail_delta:
            events.append(
                {
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": 0.0,
                    "extra": {
                        "success": False,
                        "changed_count": changed_count,
                        "error": "delta failed",
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


def test_backend_search_planned_roundtrip(tmp_path: Path) -> None:
    notebook = tmp_path / "notes"
    notebook.mkdir()
    engine = _FakeEngine()
    backend = WendaoBackend(
        notebook_dir=str(notebook),
        engine=engine,
        runtime_config=_runtime_config(),
    )

    result = asyncio.run(
        backend.search_planned("query", limit=2, options={"match_strategy": "fts", "filters": {}})
    )

    assert result["query"] == "query"
    assert len(result["hits"]) == 2
    assert result["hits"][0]["stem"] == "note-a"
    assert len(engine.search_calls) == 1
    assert json.loads(engine.search_calls[0][2])["match_strategy"] == "fts"


def test_backend_refresh_delta_fallback_to_full(tmp_path: Path) -> None:
    notebook = tmp_path / "notes"
    notebook.mkdir()
    engine = _FakeEngine()
    engine.fail_delta = True
    backend = WendaoBackend(
        notebook_dir=str(notebook),
        engine=engine,
        runtime_config=_runtime_config(),
    )

    result = asyncio.run(backend.refresh_with_delta(["docs/a.md"]))
    assert result["mode"] == "full"
    assert result["fallback"] is True
    assert engine.refresh_calls[0][1] is False
    assert engine.refresh_calls[1] == (None, True)


def test_backend_stats_reads_persistent_cache_without_engine(tmp_path: Path) -> None:
    notebook = tmp_path / "notes"
    notebook.mkdir()

    def _cache_get(_source_key: str, _ttl_sec: float) -> dict[str, object]:
        return {
            "schema": LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION,
            "source_key": backend._source_key(),
            "updated_at_unix": time.time(),
            "stats": {
                "total_notes": 7,
                "orphans": 2,
                "links_in_graph": 9,
                "nodes_in_graph": 7,
            },
        }

    backend = WendaoBackend(
        notebook_dir=str(notebook),
        runtime_config=_runtime_config(stats_ttl=300.0),
        stats_cache_getter=_cache_get,
        stats_cache_setter=lambda _source_key, _payload, _ttl_sec: None,
        stats_cache_deleter=lambda _source_key: None,
    )

    def _fail_init_engine():
        raise AssertionError("engine init should not run when persistent stats cache is valid")

    backend._init_engine = _fail_init_engine  # type: ignore[assignment]
    stats = asyncio.run(backend.stats())
    assert stats == {
        "total_notes": 7,
        "orphans": 2,
        "links_in_graph": 9,
        "nodes_in_graph": 7,
    }


def test_backend_requires_valkey_url() -> None:
    with pytest.raises(RuntimeError, match="set VALKEY_URL"):
        WendaoBackend(runtime_config=_runtime_config(cache_valkey_url=""))


def test_backend_records_cache_schema_phase_on_lazy_engine_init(tmp_path: Path) -> None:
    notebook = tmp_path / "notes"
    notebook.mkdir()
    captured: list[tuple[str, float, dict[str, object]]] = []

    def _record(phase: str, duration_ms: float, **extra: object) -> None:
        captured.append((phase, duration_ms, dict(extra)))

    backend = WendaoBackend(
        notebook_dir=str(notebook),
        runtime_config=_runtime_config(),
        phase_recorder=_record,  # type: ignore[arg-type]
        engine_factory=lambda _root, _include, _exclude: _FakeEngine(),
    )

    asyncio.run(backend.search_planned("query", limit=1, options={"filters": {}}))

    engine_phase = next((row for row in captured if row[0] == "link_graph.engine.init"), None)
    assert engine_phase is not None
    assert bool(engine_phase[2].get("success")) is True
    assert (
        str(engine_phase[2].get("cache_schema_version")) == LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION
    )
    assert str(engine_phase[2].get("cache_schema_fingerprint")) == "cafef00d"
    assert str(engine_phase[2].get("cache_status")) == "hit"
    assert str(engine_phase[2].get("cache_miss_reason")) == ""

    schema_phase = next((row for row in captured if row[0] == "link_graph.cache.schema"), None)
    assert schema_phase is not None
    assert str(schema_phase[2].get("schema_version")) == LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION
    assert str(schema_phase[2].get("schema_fingerprint")) == "cafef00d"
    assert str(schema_phase[2].get("cache_status")) == "hit"
    assert str(schema_phase[2].get("cache_miss_reason")) == ""
