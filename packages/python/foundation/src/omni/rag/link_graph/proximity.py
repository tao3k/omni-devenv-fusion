"""Common proximity boost that uses LinkGraph backend instead of skill-local logic."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omni.foundation.config.link_graph_runtime import (
    get_link_graph_proximity_max_parallel_stems,
    get_link_graph_proximity_max_stems,
    get_link_graph_proximity_neighbor_limit,
    get_link_graph_proximity_stem_cache_ttl_seconds,
    get_link_graph_proximity_timeout_seconds,
)
from omni.foundation.config.settings import get_setting

from .factory import get_link_graph_backend
from .models import LinkGraphDirection
from .policy import take_recent_graph_search_timeout

if TYPE_CHECKING:
    from .backend import LinkGraphBackend

DEFAULT_LINK_PROXIMITY_BOOST = 0.12
DEFAULT_TAG_PROXIMITY_BOOST = 0.08
DEFAULT_MAX_LINK_HOPS = 2
DEFAULT_MAX_STEMS = 8
DEFAULT_STEM_CACHE_TTL_SEC = 60.0
DEFAULT_PROXIMITY_TIMEOUT_S = 5.0
DEFAULT_MAX_PARALLEL_STEMS = 3
DEFAULT_NEIGHBOR_LIMIT_FLOOR = 12
DEFAULT_NEIGHBOR_LIMIT_CAP = 24

logger = logging.getLogger("omni.rag.link_graph.proximity")
_stem_cache: dict[tuple[str, str, str], tuple[set[str], set[str], float]] = {}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        return None


def _resolve_max_stems() -> int:
    return get_link_graph_proximity_max_stems(
        setting_reader=get_setting,
    )


def _resolve_stem_cache_ttl_seconds() -> float:
    return get_link_graph_proximity_stem_cache_ttl_seconds(
        setting_reader=get_setting,
    )


def _resolve_timeout_seconds() -> float:
    return get_link_graph_proximity_timeout_seconds(
        setting_reader=get_setting,
    )


def _resolve_max_parallel_stems(stems_count: int) -> int:
    generic = get_link_graph_proximity_max_parallel_stems(
        setting_reader=get_setting,
    )
    return min(generic, max(1, stems_count))


def _resolve_neighbor_limit(stems_count: int) -> int:
    configured = get_link_graph_proximity_neighbor_limit(
        setting_reader=get_setting,
    )
    if configured > 0:
        return configured
    auto_limit = max(DEFAULT_NEIGHBOR_LIMIT_FLOOR, stems_count * 3)
    return min(DEFAULT_NEIGHBOR_LIMIT_CAP, auto_limit)


def _is_note_stem(source_or_stem: str) -> bool:
    """True if this looks like a note stem/path, not an opaque chunk id."""
    if not source_or_stem or not source_or_stem.strip():
        return False
    value = source_or_stem.strip()
    if _UUID_RE.match(value):
        return False
    return not (len(value) == 32 and re.match(r"^[0-9a-fA-F]+$", value))


def _apply_proximity_boost_python(
    results: list[dict[str, Any]],
    stem_links: dict[str, set[str]],
    stem_tags: dict[str, set[str]],
    link_boost: float,
    tag_boost: float,
) -> list[dict[str, Any]]:
    """Pure Python fallback when Rust boost helper is unavailable."""
    for i, r1 in enumerate(results):
        stem1 = Path(r1.get("source", "")).stem
        if not stem1 or stem1 not in stem_links:
            continue
        for j, r2 in enumerate(results):
            if i >= j:
                continue
            stem2 = Path(r2.get("source", "")).stem
            if not stem2 or stem2 not in stem_links:
                continue
            if stem2 in stem_links.get(stem1, set()) or stem1 in stem_links.get(stem2, set()):
                r1["score"] = float(r1.get("score", 0)) + link_boost
                r2["score"] = float(r2.get("score", 0)) + link_boost
            shared_tags = stem_tags.get(stem1, set()) & stem_tags.get(stem2, set())
            if shared_tags:
                r1["score"] = float(r1.get("score", 0)) + tag_boost
                r2["score"] = float(r2.get("score", 0)) + tag_boost
    results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return results


async def apply_link_graph_proximity_boost(
    results: list[dict[str, Any]],
    query: str,
    *,
    backend: LinkGraphBackend | None = None,
    notebook_dir: str | Path | None = None,
    link_boost: float = DEFAULT_LINK_PROXIMITY_BOOST,
    tag_boost: float = DEFAULT_TAG_PROXIMITY_BOOST,
    max_hops: int = DEFAULT_MAX_LINK_HOPS,
    fusion_scale: float | None = None,
) -> list[dict[str, Any]]:
    """Boost recall scores based on link proximity and shared tags from link graph."""
    if not results or len(results) < 2:
        return results

    if take_recent_graph_search_timeout(query):
        _record_phase(
            "link_graph.proximity.fetch",
            0.0,
            backend="skipped",
            stems=0,
            fetched=0,
            timed_out=False,
            timeout_s=0.0,
            max_parallel=0,
            neighbor_limit=0,
            cache_ttl_s=0.0,
            skipped=True,
            reason="recent_graph_search_timeout",
        )
        return results

    effective_link_boost = link_boost
    effective_tag_boost = tag_boost
    if fusion_scale is not None:
        effective_link_boost = link_boost * fusion_scale
        effective_tag_boost = tag_boost * fusion_scale

    try:
        backend_obj = backend or get_link_graph_backend(notebook_dir=notebook_dir)
    except Exception:
        return results
    backend_name = getattr(backend_obj, "backend_name", "unknown")
    proximity_timeout_s = _resolve_timeout_seconds()
    stem_cache_ttl_s = _resolve_stem_cache_ttl_seconds()
    root_id = str(notebook_dir) if notebook_dir is not None else "<default>"

    stems = [
        Path(r.get("source", "")).stem
        for r in results
        if r.get("source") and _is_note_stem(str(r.get("source", "")))
    ]
    stems = [s for s in stems if s and _is_note_stem(s)]
    stems = list(dict.fromkeys(stems))
    max_stems = _resolve_max_stems()
    if len(stems) > max_stems:
        stems = stems[:max_stems]
    if not stems:
        return results
    max_parallel_stems = _resolve_max_parallel_stems(len(stems))
    neighbor_limit = _resolve_neighbor_limit(len(stems))

    stem_links: dict[str, set[str]] = {}
    stem_tags: dict[str, set[str]] = {}
    now = time.monotonic()
    stem_fetch_sem = asyncio.Semaphore(max_parallel_stems)

    async def _fetch_stem_context(stem: str) -> tuple[str, set[str], set[str]]:
        key = (backend_name, root_id, stem)
        cached = _stem_cache.get(key)
        if stem_cache_ttl_s > 0 and cached:
            links, tags, expires_at = cached
            if now < expires_at:
                return stem, links, tags

        async with stem_fetch_sem:
            links: set[str] = set()
            tags: set[str] = set()
            try:
                neighbors_coro = backend_obj.neighbors(
                    stem,
                    direction=LinkGraphDirection.BOTH,
                    hops=max(1, int(max_hops)),
                    limit=neighbor_limit,
                )
                if abs(effective_tag_boost) > 1e-9:
                    neighbors, meta = await asyncio.gather(
                        neighbors_coro,
                        backend_obj.metadata(stem),
                    )
                else:
                    neighbors = await neighbors_coro
                    meta = None
                links.update(n.stem for n in neighbors if _is_note_stem(n.stem))
                if meta is not None:
                    tags.update(t for t in meta.tags if str(t).strip())
            except Exception:
                pass

            if stem_cache_ttl_s > 0:
                _stem_cache[key] = (links, tags, now + stem_cache_ttl_s)
            return stem, links, tags

    fetch_started = time.perf_counter()
    timed_out = False
    tasks = [asyncio.create_task(_fetch_stem_context(stem)) for stem in stems]
    try:
        for completed in asyncio.as_completed(tasks, timeout=proximity_timeout_s):
            stem, links, tags = await completed
            stem_links[stem] = links
            stem_tags[stem] = tags
    except TimeoutError:
        timed_out = True
        logger.debug(
            "LinkGraph proximity boost partial: timeout after %ss (backend=%s, stems=%d fetched=%d)",
            proximity_timeout_s,
            backend_name,
            len(stems),
            len(stem_links),
        )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    _record_phase(
        "link_graph.proximity.fetch",
        (time.perf_counter() - fetch_started) * 1000,
        backend=backend_name,
        stems=len(stems),
        fetched=len(stem_links),
        timed_out=timed_out,
        timeout_s=round(proximity_timeout_s, 3),
        max_parallel=max_parallel_stems,
        neighbor_limit=neighbor_limit,
        cache_ttl_s=round(stem_cache_ttl_s, 3),
    )

    try:
        from omni_core_rs import apply_link_graph_proximity_boost_py
    except ImportError:
        return _apply_proximity_boost_python(
            results, stem_links, stem_tags, effective_link_boost, effective_tag_boost
        )

    rust_input = [
        {
            "source": str(r.get("source", "")),
            "score": float(r.get("score", 0)),
            "content": str(r.get("content", "")),
            "title": str(r.get("title", "")),
        }
        for r in results
    ]
    rust_output = apply_link_graph_proximity_boost_py(
        rust_input,
        {k: list(v) for k, v in stem_links.items()},
        {k: list(v) for k, v in stem_tags.items()},
        effective_link_boost,
        effective_tag_boost,
    )

    score_by_source = {row["source"]: row["score"] for row in rust_output}
    for row in results:
        src = str(row.get("source", ""))
        if src in score_by_source:
            row["score"] = score_by_source[src]
    results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return results


__all__ = ["apply_link_graph_proximity_boost"]
