"""Bindings-first Python wrapper for the xiuxian-wendao Rust engine."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RustWendaoUnavailableError(RuntimeError):
    """Raised when `omni_core_rs.PyLinkGraphEngine` is unavailable."""


def _import_rust_module() -> Any:
    try:
        return importlib.import_module("omni_core_rs")
    except Exception as exc:
        raise RustWendaoUnavailableError(
            "omni_core_rs is unavailable; install omni-core-rs before using xiuxian-wendao-py"
        ) from exc


def _import_engine_class() -> type[Any]:
    module = _import_rust_module()
    engine_cls = getattr(module, "PyLinkGraphEngine", None)
    if engine_cls is None:
        raise RustWendaoUnavailableError(
            "omni_core_rs.PyLinkGraphEngine is unavailable; verify omni-core-rs build"
        )
    return engine_cls


def _decode_json_object(raw: Any) -> dict[str, Any]:
    payload = raw
    if isinstance(raw, str):
        payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object payload from Rust engine")
    return payload


def _decode_json_list(raw: Any) -> list[dict[str, Any]]:
    payload = raw
    if isinstance(raw, str):
        payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Expected JSON list payload from Rust engine")
    return [row for row in payload if isinstance(row, dict)]


def _encode_json_object(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, sort_keys=True)


def _encode_delta_paths(changed_paths: list[str] | None) -> str | None:
    if changed_paths is None:
        return None
    normalized = [str(item).strip() for item in changed_paths if str(item).strip()]
    if not normalized:
        return json.dumps([])
    return json.dumps(normalized)


def stats_cache_get(source_key: str, ttl_sec: float) -> dict[str, Any] | None:
    module = _import_rust_module()
    fn = getattr(module, "link_graph_stats_cache_get", None)
    if not callable(fn):
        raise RustWendaoUnavailableError(
            "omni_core_rs.link_graph_stats_cache_get is unavailable; verify omni-core-rs build"
        )
    raw = fn(str(source_key), float(ttl_sec))
    if raw is None:
        return None
    return _decode_json_object(raw)


def stats_cache_set(source_key: str, stats_payload: dict[str, Any], ttl_sec: float) -> None:
    module = _import_rust_module()
    fn = getattr(module, "link_graph_stats_cache_set", None)
    if not callable(fn):
        raise RustWendaoUnavailableError(
            "omni_core_rs.link_graph_stats_cache_set is unavailable; verify omni-core-rs build"
        )
    stats_only = _decode_json_object(stats_payload).get("stats", stats_payload)
    fn(str(source_key), json.dumps(stats_only, sort_keys=True), float(ttl_sec))
    return None


def stats_cache_del(source_key: str) -> None:
    module = _import_rust_module()
    fn = getattr(module, "link_graph_stats_cache_del", None)
    if not callable(fn):
        raise RustWendaoUnavailableError(
            "omni_core_rs.link_graph_stats_cache_del is unavailable; verify omni-core-rs build"
        )
    fn(str(source_key))
    return None


@dataclass(slots=True)
class WendaoEngine:
    """Thin wrapper over `omni_core_rs.PyLinkGraphEngine`."""

    _inner: Any

    @classmethod
    def create(
        cls,
        root: str | Path,
        *,
        include_dirs: list[str] | None = None,
        excluded_dirs: list[str] | None = None,
    ) -> WendaoEngine:
        engine_cls = _import_engine_class()
        root_path = str(Path(root).expanduser())
        inner = engine_cls(
            root_path,
            include_dirs=list(include_dirs or []),
            excluded_dirs=list(excluded_dirs or []),
        )
        return cls(_inner=inner)

    @property
    def raw(self) -> Any:
        """Access the underlying rust binding object."""
        return self._inner

    def search_planned(
        self,
        query: str,
        *,
        limit: int = 20,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw = self._inner.search_planned(query, max(1, int(limit)), _encode_json_object(options))
        return _decode_json_object(raw)

    def related(
        self,
        seed: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        raw = self._inner.related(seed, max(0, int(max_distance)), max(1, int(limit)))
        return _decode_json_list(raw)

    def neighbors(
        self,
        stem: str,
        *,
        direction: str = "both",
        hops: int = 1,
        limit: int = 64,
    ) -> list[dict[str, Any]]:
        raw = self._inner.neighbors(stem, str(direction), max(1, int(hops)), max(1, int(limit)))
        return _decode_json_list(raw)

    def metadata(self, stem: str) -> dict[str, Any]:
        raw = self._inner.metadata(stem)
        return _decode_json_object(raw)

    def stats(self) -> dict[str, Any]:
        raw = self._inner.stats()
        return _decode_json_object(raw)

    def cache_schema_info(self) -> dict[str, Any]:
        info = getattr(self._inner, "cache_schema_info", None)
        if not callable(info):
            return {}
        return _decode_json_object(info())

    def toc(self, *, limit: int = 200) -> list[dict[str, Any]]:
        raw = self._inner.toc(max(1, int(limit)))
        return _decode_json_list(raw)

    def refresh(self) -> None:
        refresh_with_delta = getattr(self._inner, "refresh_with_delta", None)
        if callable(refresh_with_delta):
            refresh_with_delta(None, True)
            return None

        refresh = getattr(self._inner, "refresh", None)
        if callable(refresh):
            refresh()
            return None

        raise AttributeError(
            "Rust engine missing refresh API (expected refresh_with_delta or refresh)"
        )

    def refresh_with_delta(
        self,
        changed_paths: list[str] | None = None,
        *,
        force_full: bool = False,
    ) -> None:
        refresh_with_delta = getattr(self._inner, "refresh_with_delta", None)
        if not callable(refresh_with_delta):
            raise AttributeError("Rust engine missing refresh_with_delta API")
        refresh_with_delta(_encode_delta_paths(changed_paths), bool(force_full))
        return None

    def refresh_plan_apply(
        self,
        changed_paths: list[str] | None = None,
        *,
        force_full: bool = False,
        full_rebuild_threshold: int | None = None,
    ) -> dict[str, Any]:
        planner = getattr(self._inner, "refresh_plan_apply", None)
        if not callable(planner):
            raise AttributeError("Rust engine missing refresh_plan_apply API")
        raw = planner(
            _encode_delta_paths(changed_paths),
            bool(force_full),
            None if full_rebuild_threshold is None else max(1, int(full_rebuild_threshold)),
        )
        return _decode_json_object(raw)


def create_engine(
    root: str | Path,
    *,
    include_dirs: list[str] | None = None,
    excluded_dirs: list[str] | None = None,
) -> WendaoEngine:
    """Convenience constructor for `WendaoEngine`."""
    return WendaoEngine.create(
        root,
        include_dirs=include_dirs,
        excluded_dirs=excluded_dirs,
    )


__all__ = [
    "RustWendaoUnavailableError",
    "WendaoEngine",
    "create_engine",
    "stats_cache_del",
    "stats_cache_get",
    "stats_cache_set",
]
