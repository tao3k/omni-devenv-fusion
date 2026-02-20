"""Persistent stats cache behavior for Wendao backend."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from ...models import LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION
from ..codec import decode_json_object

logger = logging.getLogger("xiuxian_wendao_py.backend")
_STATS_CACHE_SCHEMA = LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION


class StatsCacheMixin:
    """Handle key derivation and Valkey-backed stats cache access."""

    _notebook_dir: str | None
    _notebook_root: str | None
    _include_dirs: list[str]
    _excluded_dirs: list[str]
    _runtime_config: Any
    _stats_cache_getter: Any
    _stats_cache_setter: Any
    _stats_cache_deleter: Any

    @staticmethod
    def _resolve_cache_base_key(notebook_dir: str | None, notebook_root: str | None) -> str:
        if notebook_root:
            return notebook_root
        if notebook_dir:
            return str(Path(notebook_dir).expanduser().resolve())
        return "<default>"

    def _base_key(self) -> str:
        return self._resolve_cache_base_key(self._notebook_dir, self._notebook_root)

    def _source_key(self) -> str:
        base = self._base_key()
        included = ",".join(item.lower() for item in self._include_dirs)
        excluded = ",".join(item.lower() for item in self._excluded_dirs)
        if included:
            base = f"{base}|include={included}"
        if excluded:
            return f"{base}|exclude={excluded}"
        return base

    @staticmethod
    def _normalize_engine_stats(payload: Any) -> dict[str, int] | None:
        if not isinstance(payload, dict):
            return None
        try:
            total_notes = max(0, int(payload.get("total_notes", 0) or 0))
            orphans = max(0, int(payload.get("orphans", 0) or 0))
            links_in_graph = max(0, int(payload.get("links_in_graph", 0) or 0))
            nodes_in_graph = max(0, int(payload.get("nodes_in_graph", total_notes) or total_notes))
        except (TypeError, ValueError):
            return None
        return {
            "total_notes": total_notes,
            "orphans": orphans,
            "links_in_graph": links_in_graph,
            "nodes_in_graph": nodes_in_graph,
        }

    def _resolve_stats_cache_slot_key(self) -> str:
        source = self._source_key()
        return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]

    def _resolve_stats_cache_ttl_sec(self) -> float:
        return self._runtime_config.stats_persistent_cache_ttl_sec

    def _resolve_delta_rebuild_threshold(self) -> int:
        return self._runtime_config.delta_full_rebuild_threshold

    @staticmethod
    def _normalize_changed_paths(changed_paths: Any) -> list[str]:
        if changed_paths is None:
            return []
        if isinstance(changed_paths, (str, Path)):
            values: list[Any] = [changed_paths]
        elif isinstance(changed_paths, (list, tuple, set)):
            values = list(changed_paths)
        else:
            values = []

        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
        return out

    def _invalidate_persistent_stats_cache(self) -> None:
        source_key = self._source_key()
        started_at = time.perf_counter()
        try:
            self._stats_cache_deleter(source_key)
        except Exception as exc:
            self._record_phase(
                "link_graph.stats.cache.del",
                (time.perf_counter() - started_at) * 1000.0,
                success=False,
                backend="valkey",
                key_slot=self._resolve_stats_cache_slot_key(),
                error=str(exc),
            )
            logger.debug("Wendao persistent stats cache invalidation failed: %s", exc)
            return None
        self._record_phase(
            "link_graph.stats.cache.del",
            (time.perf_counter() - started_at) * 1000.0,
            success=True,
            backend="valkey",
            key_slot=self._resolve_stats_cache_slot_key(),
        )
        return None

    def _load_persistent_stats_cache(self) -> dict[str, int] | None:
        ttl_sec = self._resolve_stats_cache_ttl_sec()
        if ttl_sec <= 0:
            return None
        source_key = self._source_key()
        started_at = time.perf_counter()
        try:
            payload = self._stats_cache_getter(source_key, ttl_sec)
        except Exception as exc:
            self._record_phase(
                "link_graph.stats.cache.get",
                (time.perf_counter() - started_at) * 1000.0,
                success=False,
                cache_hit=False,
                backend="valkey",
                key_slot=self._resolve_stats_cache_slot_key(),
                error=str(exc),
            )
            logger.debug("Wendao persistent stats cache read failed: %s", exc)
            return None
        if payload is None:
            self._record_phase(
                "link_graph.stats.cache.get",
                (time.perf_counter() - started_at) * 1000.0,
                success=True,
                cache_hit=False,
                backend="valkey",
                key_slot=self._resolve_stats_cache_slot_key(),
            )
            return None
        payload_obj = decode_json_object(payload)
        if str(payload_obj.get("schema", "")).strip() != _STATS_CACHE_SCHEMA:
            return None
        if str(payload_obj.get("source_key", "")).strip() != source_key:
            return None
        try:
            updated_at_unix = float(payload_obj.get("updated_at_unix", 0.0) or 0.0)
        except (TypeError, ValueError):
            return None
        if updated_at_unix <= 0:
            return None
        if (time.time() - updated_at_unix) > ttl_sec:
            return None
        normalized = self._normalize_engine_stats(payload_obj.get("stats"))
        self._record_phase(
            "link_graph.stats.cache.get",
            (time.perf_counter() - started_at) * 1000.0,
            success=True,
            cache_hit=bool(normalized),
            backend="valkey",
            key_slot=self._resolve_stats_cache_slot_key(),
        )
        return normalized

    def _save_persistent_stats_cache(self, stats: dict[str, int]) -> None:
        ttl_sec = self._resolve_stats_cache_ttl_sec()
        if ttl_sec <= 0:
            return None
        source_key = self._source_key()
        payload = {
            "schema": _STATS_CACHE_SCHEMA,
            "source_key": source_key,
            "updated_at_unix": float(time.time()),
            "stats": dict(stats),
        }
        started_at = time.perf_counter()
        try:
            self._stats_cache_setter(source_key, payload, ttl_sec)
        except Exception as exc:
            self._record_phase(
                "link_graph.stats.cache.set",
                (time.perf_counter() - started_at) * 1000.0,
                success=False,
                backend="valkey",
                key_slot=self._resolve_stats_cache_slot_key(),
                error=str(exc),
            )
            logger.debug("Wendao persistent stats cache write failed: %s", exc)
            return None
        self._record_phase(
            "link_graph.stats.cache.set",
            (time.perf_counter() - started_at) * 1000.0,
            success=True,
            backend="valkey",
            key_slot=self._resolve_stats_cache_slot_key(),
        )
        return None
