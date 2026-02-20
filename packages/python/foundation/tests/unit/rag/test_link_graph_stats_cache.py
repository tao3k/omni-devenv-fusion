"""Tests for LinkGraph stats cache and timeout fallback."""

from __future__ import annotations

import asyncio

import pytest

from omni.rag.link_graph.stats_cache import (
    clear_link_graph_stats_cache,
    get_cached_link_graph_stats,
    get_link_graph_stats_for_response,
    schedule_link_graph_stats_refresh,
)


class _StatsBackend:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.delay_sec = 0.0
        self.payload = {
            "total_notes": 10,
            "orphans": 1,
            "links_in_graph": 9,
            "nodes_in_graph": 10,
        }

    async def stats(self) -> dict[str, int]:
        self.calls += 1
        if self.delay_sec > 0:
            await asyncio.sleep(self.delay_sec)
        if self.fail:
            raise RuntimeError("stats failed")
        return dict(self.payload)


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_uses_cache() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()

    first = await get_cached_link_graph_stats(backend, ttl_sec=60.0, timeout_sec=1.0)
    second = await get_cached_link_graph_stats(backend, ttl_sec=60.0, timeout_sec=1.0)

    assert first["total_notes"] == 10
    assert second["total_notes"] == 10
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_fallbacks_to_cache_on_error() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()

    first = await get_cached_link_graph_stats(backend, ttl_sec=60.0, timeout_sec=1.0)
    assert first["total_notes"] == 10

    backend.fail = True
    fallback = await get_cached_link_graph_stats(
        backend,
        ttl_sec=60.0,
        timeout_sec=1.0,
        force_refresh=True,
    )
    assert fallback["total_notes"] == 10
    assert backend.calls == 2


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_timeout_returns_default_without_cache() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()
    backend.delay_sec = 0.2

    out = await get_cached_link_graph_stats(
        backend,
        ttl_sec=60.0,
        timeout_sec=0.01,
        default={"total_notes": 0, "orphans": 0, "links_in_graph": 0, "nodes_in_graph": 0},
    )
    assert out["total_notes"] == 0


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_normalizes_partial_default_shape() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()
    backend.delay_sec = 0.2

    out = await get_cached_link_graph_stats(
        backend,
        ttl_sec=60.0,
        timeout_sec=0.01,
        default={"total_notes": 7},
    )
    assert out == {
        "total_notes": 7,
        "orphans": 0,
        "links_in_graph": 0,
        "nodes_in_graph": 0,
    }


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_can_skip_backend_refresh() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()

    out = await get_cached_link_graph_stats(
        backend,
        ttl_sec=60.0,
        allow_refresh=False,
        default={},
    )
    assert out == {
        "total_notes": 0,
        "orphans": 0,
        "links_in_graph": 0,
        "nodes_in_graph": 0,
    }
    assert backend.calls == 0


@pytest.mark.asyncio
async def test_get_cached_link_graph_stats_returns_stale_cache_when_refresh_disabled() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()

    first = await get_cached_link_graph_stats(backend, ttl_sec=0.01, timeout_sec=1.0)
    assert first["total_notes"] == 10
    await asyncio.sleep(0.02)

    backend.payload["total_notes"] = 20
    stale = await get_cached_link_graph_stats(
        backend,
        ttl_sec=0.01,
        allow_refresh=False,
        default={},
    )
    assert stale["total_notes"] == 10
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_schedule_link_graph_stats_refresh_populates_cache() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()
    backend.delay_sec = 0.03

    scheduled = schedule_link_graph_stats_refresh(backend, ttl_sec=60.0, timeout_sec=1.0)
    duplicate = schedule_link_graph_stats_refresh(backend, ttl_sec=60.0, timeout_sec=1.0)
    assert scheduled is True
    assert duplicate is False

    await asyncio.sleep(0.25)
    cached = await get_cached_link_graph_stats(
        backend, ttl_sec=60.0, allow_refresh=False, default={}
    )
    assert cached["total_notes"] == 10
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_get_link_graph_stats_for_response_fast_probe_timeout_schedules_refresh() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()
    backend.delay_sec = 0.2

    first = await get_link_graph_stats_for_response(
        backend,
        ttl_sec=60.0,
        probe_timeout_sec=0.01,
        refresh_timeout_sec=1.0,
    )
    assert first == {
        "total_notes": 0,
        "orphans": 0,
        "links_in_graph": 0,
        "nodes_in_graph": 0,
    }

    await asyncio.sleep(0.25)
    warm = await get_cached_link_graph_stats(
        backend,
        ttl_sec=60.0,
        allow_refresh=False,
        default={},
    )
    assert warm["total_notes"] == 10


@pytest.mark.asyncio
async def test_get_link_graph_stats_for_response_include_meta_probe_then_cache() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()

    first_stats, first_meta = await get_link_graph_stats_for_response(
        backend,
        ttl_sec=60.0,
        probe_timeout_sec=1.0,
        include_meta=True,
    )
    assert first_stats["total_notes"] == 10
    assert first_meta["source"] == "probe"
    assert first_meta["cache_hit"] is False
    assert first_meta["fresh"] is True
    assert first_meta["refresh_scheduled"] is False

    second_stats, second_meta = await get_link_graph_stats_for_response(
        backend,
        ttl_sec=60.0,
        include_meta=True,
    )
    assert second_stats["total_notes"] == 10
    assert second_meta["source"] == "cache"
    assert second_meta["cache_hit"] is True
    assert second_meta["fresh"] is True
    assert backend.calls == 1


@pytest.mark.asyncio
async def test_get_link_graph_stats_for_response_include_meta_fallback_then_refresh() -> None:
    clear_link_graph_stats_cache()
    backend = _StatsBackend()
    backend.delay_sec = 0.2

    first_stats, first_meta = await get_link_graph_stats_for_response(
        backend,
        ttl_sec=60.0,
        probe_timeout_sec=0.01,
        refresh_timeout_sec=1.0,
        include_meta=True,
    )
    assert first_stats["total_notes"] == 0
    assert first_meta["source"] == "fallback"
    assert first_meta["cache_hit"] is False
    assert first_meta["fresh"] is False
    assert first_meta["refresh_scheduled"] is True

    await asyncio.sleep(0.25)
    second_stats, second_meta = await get_link_graph_stats_for_response(
        backend,
        ttl_sec=60.0,
        include_meta=True,
    )
    assert second_stats["total_notes"] == 10
    assert second_meta["source"] == "cache"
