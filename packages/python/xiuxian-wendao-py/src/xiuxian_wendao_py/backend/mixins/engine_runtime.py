"""Engine/runtime lifecycle methods for Wendao backend."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...engine import create_engine
from ...models import (
    LINK_GRAPH_CACHE_VALKEY_URL_ENV,
    LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION,
    LINK_GRAPH_VALKEY_KEY_PREFIX_ENV,
    LINK_GRAPH_VALKEY_TTL_SECONDS_ENV,
)
from ..codec import decode_json_object

if TYPE_CHECKING:
    from ...models import WendaoRuntimeConfig

logger = logging.getLogger("xiuxian_wendao_py.backend")


class EngineRuntimeMixin:
    """Handle runtime config hydration, env wiring, and engine lifecycle."""

    _notebook_dir: str | None
    _notebook_root: str | None
    _engine: Any | None
    _engine_init_attempted: bool
    _engine_factory: Any
    _runtime_config: WendaoRuntimeConfig
    _runtime_config_loader: Any
    _settings_reloader: Any
    _include_dirs_resolver: Any
    _excluded_dirs_resolver: Any
    _include_dirs: list[str]
    _excluded_dirs: list[str]

    def _reload_runtime_config_if_cache_url_missing(self) -> None:
        current = str(self._runtime_config.cache_valkey_url or "").strip()
        if current:
            return None
        if self._runtime_config_loader is None or self._settings_reloader is None:
            return None
        self._settings_reloader()
        self._runtime_config = self._runtime_config_loader()
        return None

    def _require_cache_valkey_url(self) -> str:
        value = str(self._runtime_config.cache_valkey_url or "").strip()
        if value:
            return value
        raise RuntimeError(
            "link_graph cache valkey url is required (set VALKEY_URL or link_graph.cache.valkey_url)"
        )

    def _ensure_engine(self) -> Any | None:
        if self._engine is not None:
            return self._engine
        if self._engine_init_attempted:
            return None
        self._engine_init_attempted = True
        self._engine = self._init_engine()
        return self._engine

    def _require_engine(self) -> Any:
        engine = self._engine if self._engine is not None else self._ensure_engine()
        if engine is None:
            raise RuntimeError("Wendao rust engine unavailable")
        return engine

    def _resolve_notebook_root(self) -> str | None:
        if self._notebook_dir:
            candidate = Path(self._notebook_dir).expanduser()
            if candidate.exists() and candidate.is_dir():
                return str(candidate.resolve())
        raw = self._runtime_config.root_dir
        if not raw:
            return None
        candidate = Path(raw).expanduser()
        if candidate.exists() and candidate.is_dir():
            return str(candidate.resolve())
        return None

    def _init_engine(self) -> Any | None:
        started_at = time.perf_counter()
        root = self._notebook_root
        if not root:
            self._record_phase(
                "link_graph.engine.init",
                (time.perf_counter() - started_at) * 1000.0,
                success=False,
                reason="root_unavailable",
            )
            return None
        include_dirs = list(self._include_dirs)
        excluded_dirs = list(self._excluded_dirs)
        try:
            if self._engine_factory is not None:
                engine = self._engine_factory(root, include_dirs, excluded_dirs)
            else:
                engine = create_engine(
                    root,
                    include_dirs=include_dirs,
                    excluded_dirs=excluded_dirs,
                ).raw
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            self._record_phase(
                "link_graph.engine.init",
                duration_ms,
                success=False,
                reason="engine_unavailable",
                error=str(exc),
            )
            logger.debug("Wendao rust engine unavailable: %s", exc)
            return None

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        if engine is None:
            self._record_phase(
                "link_graph.engine.init",
                duration_ms,
                success=False,
                reason="engine_unavailable",
            )
            return None

        schema_info = self._resolve_cache_schema_info(engine)
        self._record_phase(
            "link_graph.engine.init",
            duration_ms,
            success=True,
            engine_reused=False,
            cache_schema_version=schema_info["schema_version"],
            cache_schema_fingerprint=schema_info["schema_fingerprint"],
            cache_schema_source=schema_info["schema_source"],
            cache_status=schema_info["cache_status"],
            cache_miss_reason=schema_info["cache_miss_reason"],
        )
        self._record_phase(
            "link_graph.cache.schema",
            0.0,
            schema_version=schema_info["schema_version"],
            schema_fingerprint=schema_info["schema_fingerprint"],
            schema_source=schema_info["schema_source"],
            cache_status=schema_info["cache_status"],
            cache_miss_reason=schema_info["cache_miss_reason"],
        )
        return engine

    @staticmethod
    def _fallback_cache_schema_fingerprint(schema_version: str) -> str:
        return hashlib.sha1(schema_version.encode("utf-8")).hexdigest()[:16]

    def _resolve_cache_schema_info(self, engine: Any) -> dict[str, str]:
        schema_version = LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION
        schema_fingerprint = self._fallback_cache_schema_fingerprint(schema_version)
        schema_source = "python_fallback"
        cache_status = "unknown"
        cache_miss_reason = ""

        resolver = getattr(engine, "cache_schema_info", None)
        if not callable(resolver):
            return {
                "schema_version": schema_version,
                "schema_fingerprint": schema_fingerprint,
                "schema_source": schema_source,
                "cache_status": cache_status,
                "cache_miss_reason": cache_miss_reason,
            }

        try:
            payload = decode_json_object(resolver())
        except Exception as exc:
            logger.debug("Wendao cache_schema_info unavailable: %s", exc)
            return {
                "schema_version": schema_version,
                "schema_fingerprint": schema_fingerprint,
                "schema_source": schema_source,
                "cache_status": cache_status,
                "cache_miss_reason": cache_miss_reason,
            }

        reported_version = str(payload.get("schema_version") or "").strip()
        if reported_version:
            schema_version = reported_version
        reported_fingerprint = str(payload.get("schema_fingerprint") or "").strip()
        if reported_fingerprint:
            schema_fingerprint = reported_fingerprint
            schema_source = "rust"
        else:
            schema_fingerprint = self._fallback_cache_schema_fingerprint(schema_version)
            schema_source = "rust_missing_fingerprint"
        reported_status = str(payload.get("cache_status") or "").strip().lower()
        if reported_status in {"hit", "miss"}:
            cache_status = reported_status
        reported_reason = str(payload.get("cache_miss_reason") or "").strip()
        if reported_reason:
            cache_miss_reason = reported_reason
        return {
            "schema_version": schema_version,
            "schema_fingerprint": schema_fingerprint,
            "schema_source": schema_source,
            "cache_status": cache_status,
            "cache_miss_reason": cache_miss_reason,
        }

    def _emit_schema_signal_for_explicit_engine(self) -> None:
        if self._engine is None:
            return None
        schema_info = self._resolve_cache_schema_info(self._engine)
        self._record_phase(
            "link_graph.engine.init",
            0.0,
            success=True,
            engine_reused=True,
            cache_schema_version=schema_info["schema_version"],
            cache_schema_fingerprint=schema_info["schema_fingerprint"],
            cache_schema_source=schema_info["schema_source"],
            cache_status=schema_info["cache_status"],
            cache_miss_reason=schema_info["cache_miss_reason"],
        )
        self._record_phase(
            "link_graph.cache.schema",
            0.0,
            schema_version=schema_info["schema_version"],
            schema_fingerprint=schema_info["schema_fingerprint"],
            schema_source=schema_info["schema_source"],
            cache_status=schema_info["cache_status"],
            cache_miss_reason=schema_info["cache_miss_reason"],
        )
        return None

    def _configure_rust_cache_env(self) -> None:
        os.environ[LINK_GRAPH_CACHE_VALKEY_URL_ENV] = self._require_cache_valkey_url()

        if self._runtime_config.cache_key_prefix:
            os.environ[LINK_GRAPH_VALKEY_KEY_PREFIX_ENV] = self._runtime_config.cache_key_prefix

        if self._runtime_config.cache_ttl_seconds:
            os.environ[LINK_GRAPH_VALKEY_TTL_SECONDS_ENV] = self._runtime_config.cache_ttl_seconds

    def _resolve_include_dirs(self) -> list[str]:
        return self._include_dirs_resolver(self._runtime_config, self._notebook_root)

    def _resolve_excluded_dirs(self) -> list[str]:
        return list(self._excluded_dirs_resolver(self._runtime_config))
