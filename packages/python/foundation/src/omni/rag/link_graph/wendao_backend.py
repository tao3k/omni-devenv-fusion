"""Wendao LinkGraph bridge.

Foundation keeps the public LinkGraph contract surface and delegates runtime
mechanics to the standalone `xiuxian-wendao-py` backend core.
"""

from __future__ import annotations

import logging
from typing import Any

from omni.foundation.config.link_graph_runtime import (
    LINK_GRAPH_CACHE_VALKEY_URL_ENV,
    LINK_GRAPH_VALKEY_KEY_PREFIX_ENV,
    LINK_GRAPH_VALKEY_TTL_SECONDS_ENV,
    LinkGraphRuntimeConfig,
    get_link_graph_runtime_config,
    resolve_link_graph_include_dirs,
)
from omni.foundation.config.settings import get_setting
from xiuxian_wendao_py.backend import WendaoBackend
from xiuxian_wendao_py.models import WendaoRuntimeConfig

from .models import (
    LinkGraphDirection,
    LinkGraphHit,
    LinkGraphMetadata,
    LinkGraphNeighbor,
    LinkGraphSearchOptions,
)

logger = logging.getLogger("omni.rag.link_graph.wendao_backend")


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        return None


class WendaoLinkGraphBackend(WendaoBackend):
    """Foundation adapter that maps LinkGraph contract calls to standalone Wendao core."""

    backend_name = "wendao"

    def __init__(self, notebook_dir: str | None = None, *, engine: Any | None = None) -> None:
        super().__init__(
            notebook_dir=notebook_dir,
            engine=engine,
            runtime_config=self._load_runtime_config(),
            runtime_config_loader=self._load_runtime_config,
            include_dirs_resolver=self._resolve_include_dirs_from_runtime,
            excluded_dirs_resolver=self._resolve_excluded_dirs_from_runtime,
            phase_recorder=_record_phase,
            settings_reloader=self._reload_settings,
        )

    @staticmethod
    def _reload_settings() -> None:
        from omni.foundation.config.settings import Settings

        Settings().reload()

    @staticmethod
    def _to_runtime_config(runtime: LinkGraphRuntimeConfig) -> WendaoRuntimeConfig:
        return WendaoRuntimeConfig(
            root_dir=runtime.root_dir,
            include_dirs=list(runtime.include_dirs),
            include_dirs_auto=runtime.include_dirs_auto,
            include_dirs_auto_candidates=list(runtime.include_dirs_auto_candidates),
            exclude_dirs=list(runtime.exclude_dirs),
            stats_persistent_cache_ttl_sec=runtime.stats_persistent_cache_ttl_sec,
            delta_full_rebuild_threshold=runtime.delta_full_rebuild_threshold,
            cache_valkey_url=runtime.cache_valkey_url,
            cache_key_prefix=runtime.cache_key_prefix,
            cache_ttl_seconds=runtime.cache_ttl_seconds,
        )

    @classmethod
    def _load_runtime_config(cls) -> WendaoRuntimeConfig:
        runtime = get_link_graph_runtime_config(setting_reader=get_setting)
        return cls._to_runtime_config(runtime)

    @staticmethod
    def _resolve_include_dirs_from_runtime(
        runtime: WendaoRuntimeConfig,
        notebook_root: str | None,
    ) -> list[str]:
        return resolve_link_graph_include_dirs(
            runtime.include_dirs,
            notebook_root=notebook_root,
            include_dirs_auto=runtime.include_dirs_auto,
            auto_candidates_raw=runtime.include_dirs_auto_candidates,
        )

    @staticmethod
    def _resolve_excluded_dirs_from_runtime(runtime: WendaoRuntimeConfig) -> list[str]:
        return list(runtime.exclude_dirs)

    @staticmethod
    def _normalize_search_options(
        options: LinkGraphSearchOptions | dict[str, Any] | None,
    ) -> LinkGraphSearchOptions:
        if isinstance(options, LinkGraphSearchOptions):
            return options
        if isinstance(options, dict):
            return LinkGraphSearchOptions.from_dict(options)
        return LinkGraphSearchOptions()

    @staticmethod
    def _normalize_direction(value: str) -> LinkGraphDirection:
        raw = str(value or "both").strip().lower()
        if raw in {"incoming", "to"}:
            return LinkGraphDirection.INCOMING
        if raw in {"outgoing", "from"}:
            return LinkGraphDirection.OUTGOING
        return LinkGraphDirection.BOTH

    async def search_planned(
        self,
        query: str,
        limit: int = 20,
        options: LinkGraphSearchOptions | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_search_options(options)
        payload = normalized.to_record()
        payload.pop("schema", None)

        core_result = await super().search_planned(query=query, limit=limit, options=payload)

        planned_options_raw = core_result.get("search_options")
        options_model = LinkGraphSearchOptions.from_dict(
            planned_options_raw if isinstance(planned_options_raw, dict) else {}
        )
        planned_options = options_model.to_record()
        planned_options.pop("schema", None)

        hits: list[LinkGraphHit] = []
        for row in core_result.get("hits") if isinstance(core_result.get("hits"), list) else []:
            if not isinstance(row, dict):
                continue
            stem = str(row.get("stem") or row.get("id") or "").strip()
            if not stem:
                continue
            try:
                score = float(row.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            hits.append(
                LinkGraphHit(
                    stem=stem,
                    score=max(0.0, score),
                    title=str(row.get("title") or ""),
                    path=str(row.get("path") or ""),
                    best_section=str(row.get("best_section") or ""),
                    match_reason=str(row.get("match_reason") or ""),
                )
            )

        return {
            "query": str(core_result.get("query") or str(query)),
            "search_options": planned_options,
            "hits": hits[: max(1, int(limit))],
        }

    async def neighbors(
        self,
        stem: str,
        *,
        direction: LinkGraphDirection = LinkGraphDirection.BOTH,
        hops: int = 1,
        limit: int = 50,
    ) -> list[LinkGraphNeighbor]:
        rows = await super().neighbors(
            stem=stem,
            direction=direction.value,
            hops=hops,
            limit=limit,
        )
        out: list[LinkGraphNeighbor] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            neigh_stem = str(row.get("stem") or row.get("id") or "").strip()
            if not neigh_stem:
                continue
            try:
                distance = max(1, int(row.get("distance", 1)))
            except (TypeError, ValueError):
                distance = 1
            out.append(
                LinkGraphNeighbor(
                    stem=neigh_stem,
                    direction=self._normalize_direction(str(row.get("direction") or "both")),
                    distance=distance,
                    title=str(row.get("title") or ""),
                    path=str(row.get("path") or ""),
                )
            )
        return out[: max(1, int(limit))]

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[LinkGraphNeighbor]:
        rows = await super().related(stem=stem, max_distance=max_distance, limit=limit)
        out: list[LinkGraphNeighbor] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            neigh_stem = str(row.get("stem") or row.get("id") or "").strip()
            if not neigh_stem:
                continue
            try:
                distance = max(1, int(row.get("distance", 1)))
            except (TypeError, ValueError):
                distance = 1
            out.append(
                LinkGraphNeighbor(
                    stem=neigh_stem,
                    direction=LinkGraphDirection.BOTH,
                    distance=distance,
                    title=str(row.get("title") or ""),
                    path=str(row.get("path") or ""),
                )
            )
        return out[: max(1, int(limit))]

    async def metadata(self, stem: str) -> LinkGraphMetadata | None:
        payload = await super().metadata(stem)
        if not isinstance(payload, dict):
            return None
        meta_stem = str(payload.get("stem") or stem).strip()
        if not meta_stem:
            return None
        tags_raw = payload.get("tags")
        tags = [str(t) for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
        return LinkGraphMetadata(
            stem=meta_stem,
            tags=tags,
            title=str(payload.get("title") or ""),
            path=str(payload.get("path") or ""),
        )

    async def create_note(
        self,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> object | None:
        del title, body, tags
        return None


__all__ = [
    "LINK_GRAPH_CACHE_VALKEY_URL_ENV",
    "LINK_GRAPH_VALKEY_KEY_PREFIX_ENV",
    "LINK_GRAPH_VALKEY_TTL_SECONDS_ENV",
    "WendaoLinkGraphBackend",
]
