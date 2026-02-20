"""Common stats cache for LinkGraph backends used by fast-path searches."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from omni.foundation.config.link_graph_runtime import (
    get_link_graph_stats_cache_ttl_sec,
    get_link_graph_stats_response_probe_timeout_sec,
    get_link_graph_stats_response_refresh_timeout_sec,
    get_link_graph_stats_timeout_sec,
)


@dataclass(frozen=True)
class _StatsCacheEntry:
    stats: dict[str, int]
    expires_at_monotonic: float
    updated_at_monotonic: float


_STATS_CACHE: dict[int, _StatsCacheEntry] = {}
_STATS_REFRESH_TASKS: dict[int, asyncio.Task[None]] = {}
_EMPTY_STATS: dict[str, int] = {
    "total_notes": 0,
    "orphans": 0,
    "links_in_graph": 0,
    "nodes_in_graph": 0,
}


def _resolve_ttl(ttl_sec: float | None) -> float:
    if ttl_sec is not None:
        try:
            return max(0.0, float(ttl_sec))
        except (TypeError, ValueError):
            return 0.0
    return get_link_graph_stats_cache_ttl_sec()


def _resolve_timeout(timeout_sec: float | None) -> float:
    if timeout_sec is not None:
        try:
            return max(0.0, float(timeout_sec))
        except (TypeError, ValueError):
            return 0.0
    return get_link_graph_stats_timeout_sec()


def _resolve_response_probe_timeout(timeout_sec: float | None) -> float:
    if timeout_sec is not None:
        try:
            return max(0.0, float(timeout_sec))
        except (TypeError, ValueError):
            return 0.0
    return get_link_graph_stats_response_probe_timeout_sec()


def _resolve_response_refresh_timeout(timeout_sec: float | None) -> float:
    if timeout_sec is not None:
        try:
            return max(0.0, float(timeout_sec))
        except (TypeError, ValueError):
            return 0.0
    return get_link_graph_stats_response_refresh_timeout_sec()


def _normalize_stats(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key in ("total_notes", "orphans", "links_in_graph", "nodes_in_graph"):
        try:
            out[key] = max(0, int(raw.get(key, 0) or 0))
        except (TypeError, ValueError):
            out[key] = 0
    return out


def _cache_age_ms(entry: _StatsCacheEntry, now: float) -> int:
    return max(0, int((now - entry.updated_at_monotonic) * 1000))


def _build_stats_meta(
    *,
    source: str,
    cache_hit: bool,
    fresh: bool,
    age_ms: int,
    refresh_scheduled: bool,
) -> dict[str, Any]:
    return {
        "source": source,
        "cache_hit": bool(cache_hit),
        "fresh": bool(fresh),
        "age_ms": max(0, int(age_ms)),
        "refresh_scheduled": bool(refresh_scheduled),
    }


def _cache_entry(stats: dict[str, int], *, now: float, ttl: float) -> _StatsCacheEntry:
    return _StatsCacheEntry(
        stats=dict(stats),
        expires_at_monotonic=now + ttl,
        updated_at_monotonic=now,
    )


async def get_cached_link_graph_stats(
    backend: Any,
    *,
    ttl_sec: float | None = None,
    timeout_sec: float | None = None,
    default: dict[str, int] | None = None,
    force_refresh: bool = False,
    allow_refresh: bool = True,
) -> dict[str, int]:
    """Fetch backend stats with cache and timeout fallback."""
    now = time.monotonic()
    key = id(backend)
    ttl = _resolve_ttl(ttl_sec)
    fallback = _normalize_stats(default if isinstance(default, dict) else _EMPTY_STATS)
    cached = _STATS_CACHE.get(key)

    if ttl > 0 and not force_refresh and cached and now < cached.expires_at_monotonic:
        return dict(cached.stats)
    if not allow_refresh:
        if cached:
            return dict(cached.stats)
        return fallback

    timeout = _resolve_timeout(timeout_sec)
    try:
        if timeout > 0:
            raw = await asyncio.wait_for(backend.stats(), timeout=timeout)
        else:
            raw = await backend.stats()
        normalized = _normalize_stats(raw)
        if ttl > 0:
            _STATS_CACHE[key] = _cache_entry(normalized, now=now, ttl=ttl)
        return normalized
    except Exception:
        if cached:
            return dict(cached.stats)
        return fallback


def schedule_link_graph_stats_refresh(
    backend: Any,
    *,
    ttl_sec: float | None = None,
    timeout_sec: float | None = None,
) -> bool:
    """Schedule background stats refresh if no active refresh is in-flight."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False

    key = id(backend)
    in_flight = _STATS_REFRESH_TASKS.get(key)
    if in_flight and not in_flight.done():
        return False

    async def _refresh() -> None:
        try:
            await get_cached_link_graph_stats(
                backend,
                ttl_sec=ttl_sec,
                timeout_sec=timeout_sec,
                force_refresh=True,
                allow_refresh=True,
                default={},
            )
        except Exception:
            return None
        finally:
            _STATS_REFRESH_TASKS.pop(key, None)
        return None

    task = loop.create_task(_refresh())
    _STATS_REFRESH_TASKS[key] = task
    return True


async def get_link_graph_stats_for_response(
    backend: Any,
    *,
    ttl_sec: float | None = None,
    probe_timeout_sec: float | None = None,
    refresh_timeout_sec: float | None = None,
    fallback: dict[str, int] | None = None,
    include_meta: bool = False,
) -> dict[str, int] | tuple[dict[str, int], dict[str, Any]]:
    """Return stable stats shape for API responses with fast probe + async refresh on miss."""
    now = time.monotonic()
    key = id(backend)
    ttl = _resolve_ttl(ttl_sec)
    fallback_stats = _normalize_stats(fallback if isinstance(fallback, dict) else _EMPTY_STATS)
    cached = _STATS_CACHE.get(key)

    def _with_meta(
        stats: dict[str, int],
        meta: dict[str, Any],
    ) -> dict[str, int] | tuple[dict[str, int], dict[str, Any]]:
        if include_meta:
            return (dict(stats), dict(meta))
        return dict(stats)

    if ttl > 0 and cached and now < cached.expires_at_monotonic:
        return _with_meta(
            dict(cached.stats),
            _build_stats_meta(
                source="cache",
                cache_hit=True,
                fresh=True,
                age_ms=_cache_age_ms(cached, now),
                refresh_scheduled=False,
            ),
        )

    timeout = _resolve_response_probe_timeout(probe_timeout_sec)
    try:
        if timeout > 0:
            raw = await asyncio.wait_for(backend.stats(), timeout=timeout)
        else:
            raw = await backend.stats()
        normalized = _normalize_stats(raw)
        if ttl > 0:
            _STATS_CACHE[key] = _cache_entry(normalized, now=now, ttl=ttl)
        return _with_meta(
            normalized,
            _build_stats_meta(
                source="probe",
                cache_hit=False,
                fresh=True,
                age_ms=0,
                refresh_scheduled=False,
            ),
        )
    except Exception:
        refresh_scheduled = schedule_link_graph_stats_refresh(
            backend,
            ttl_sec=ttl,
            timeout_sec=_resolve_response_refresh_timeout(refresh_timeout_sec),
        )
        stale = _STATS_CACHE.get(key)
        if stale is not None:
            return _with_meta(
                dict(stale.stats),
                _build_stats_meta(
                    source="cache_stale",
                    cache_hit=True,
                    fresh=False,
                    age_ms=_cache_age_ms(stale, now),
                    refresh_scheduled=refresh_scheduled,
                ),
            )
        return _with_meta(
            fallback_stats,
            _build_stats_meta(
                source="fallback",
                cache_hit=False,
                fresh=False,
                age_ms=0,
                refresh_scheduled=refresh_scheduled,
            ),
        )


def clear_link_graph_stats_cache() -> None:
    """Clear process-local stats cache (for tests/runtime reset)."""
    for task in _STATS_REFRESH_TASKS.values():
        task.cancel()
    _STATS_REFRESH_TASKS.clear()
    _STATS_CACHE.clear()


__all__ = [
    "clear_link_graph_stats_cache",
    "get_cached_link_graph_stats",
    "get_link_graph_stats_for_response",
    "schedule_link_graph_stats_refresh",
]
