"""Composable core backend class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..engine import stats_cache_del, stats_cache_get, stats_cache_set
from .config import (
    default_runtime_config_from_env,
    resolve_excluded_dirs,
    resolve_include_dirs,
)
from .mixins import (
    EngineRuntimeMixin,
    QueryMixin,
    RefreshMixin,
    StatsCacheMixin,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..models import WendaoRuntimeConfig


def _default_record_phase(_phase: str, _duration_ms: float, **_extra: Any) -> None:
    return None


class WendaoBackend(
    EngineRuntimeMixin,
    StatsCacheMixin,
    RefreshMixin,
    QueryMixin,
):
    """Reusable backend core that talks to rust bindings and owns runtime mechanics."""

    backend_name = "wendao"

    def __init__(
        self,
        notebook_dir: str | None = None,
        *,
        engine: Any | None = None,
        runtime_config: WendaoRuntimeConfig | None = None,
        runtime_config_loader: Callable[[], WendaoRuntimeConfig] | None = None,
        include_dirs_resolver: Callable[[WendaoRuntimeConfig, str | None], list[str]] | None = None,
        excluded_dirs_resolver: Callable[[WendaoRuntimeConfig], list[str]] | None = None,
        phase_recorder: Callable[[str, float], None] | None = None,
        settings_reloader: Callable[[], None] | None = None,
        engine_factory: Callable[[str, list[str], list[str]], Any] | None = None,
        stats_cache_getter: Callable[[str, float], dict[str, Any] | None] | None = None,
        stats_cache_setter: Callable[[str, dict[str, Any], float], None] | None = None,
        stats_cache_deleter: Callable[[str], None] | None = None,
    ) -> None:
        self._notebook_dir = notebook_dir
        self._engine = engine
        self._engine_explicit = engine is not None
        self._engine_init_attempted = engine is not None

        self._runtime_config_loader = runtime_config_loader
        self._runtime_config = runtime_config or (
            runtime_config_loader()
            if runtime_config_loader is not None
            else default_runtime_config_from_env()
        )
        self._settings_reloader = settings_reloader

        self._include_dirs_resolver = include_dirs_resolver or (
            lambda cfg, root: resolve_include_dirs(
                cfg.include_dirs,
                notebook_root=root,
                include_dirs_auto=cfg.include_dirs_auto,
                auto_candidates_raw=cfg.include_dirs_auto_candidates,
            )
        )
        self._excluded_dirs_resolver = excluded_dirs_resolver or (
            lambda cfg: resolve_excluded_dirs(cfg.exclude_dirs)
        )
        self._phase_recorder = phase_recorder or _default_record_phase
        self._engine_factory = engine_factory
        self._stats_cache_getter = stats_cache_getter or stats_cache_get
        self._stats_cache_setter = stats_cache_setter or stats_cache_set
        self._stats_cache_deleter = stats_cache_deleter or stats_cache_del

        self._reload_runtime_config_if_cache_url_missing()
        self._configure_rust_cache_env()

        self._notebook_root = self._resolve_notebook_root()
        self._include_dirs = self._resolve_include_dirs()
        self._excluded_dirs = self._resolve_excluded_dirs()
        self._emit_schema_signal_for_explicit_engine()

    def _record_phase(self, phase: str, duration_ms: float, **extra: Any) -> None:
        try:
            self._phase_recorder(phase, duration_ms, **extra)
        except Exception:
            return None
