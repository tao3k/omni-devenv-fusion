"""Runtime defaults and resolvers for LinkGraph backends."""

from __future__ import annotations

import math
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from .settings import get_setting

# Wendao runtime config path default.
DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH: Final[str] = ".wendao/config.toml"
DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS: Final[tuple[str, ...]] = (
    ".git",
    ".cache",
    ".devenv",
    ".run",
    ".venv",
)
DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS: Final[tuple[str, ...]] = (
    "target",
    "node_modules",
)
LINK_GRAPH_CACHE_VALKEY_URL_ENV: Final[str] = "VALKEY_URL"
LINK_GRAPH_VALKEY_KEY_PREFIX_ENV: Final[str] = "OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX"
LINK_GRAPH_VALKEY_TTL_SECONDS_ENV: Final[str] = "OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS"
DEFAULT_LINK_GRAPH_BACKEND: Final[str] = "wendao"
DEFAULT_LINK_GRAPH_RETRIEVAL_MODE: Final[str] = "hybrid"
DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER: Final[int] = 4
DEFAULT_LINK_GRAPH_MAX_SOURCES: Final[int] = 8
DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS: Final[int] = 2
DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE: Final[float] = 0.25
DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE: Final[int] = 8
DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS: Final[float] = 20.0
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SECONDS: Final[float] = 3.0
DEFAULT_LINK_GRAPH_POLICY_TIMEOUT_MARKER_TTL_SECONDS: Final[float] = 8.0
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_MACHINE_LIKE: Final[float] = 0.5
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SYMBOL_HEAVY: Final[float] = 0.65
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SHORT: Final[float] = 0.85
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_LONG_NATURAL: Final[float] = 1.0
DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_DEFAULT: Final[float] = 1.0
DEFAULT_LINK_GRAPH_PROXIMITY_MAX_STEMS: Final[int] = 8
DEFAULT_LINK_GRAPH_PROXIMITY_STEM_CACHE_TTL_SECONDS: Final[float] = 60.0
DEFAULT_LINK_GRAPH_PROXIMITY_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_LINK_GRAPH_PROXIMITY_MAX_PARALLEL_STEMS: Final[int] = 3
DEFAULT_LINK_GRAPH_PROXIMITY_NEIGHBOR_LIMIT: Final[int] = 0
DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC: Final[float] = 60.0
DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC: Final[float] = 0.2
DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC: Final[float] = 0.05
DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC: Final[float] = 5.0
DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC: Final[float] = 120.0
DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD: Final[int] = 256


@dataclass(frozen=True, slots=True)
class LinkGraphRuntimeConfig:
    """Unified LinkGraph runtime config resolved from settings + env."""

    root_dir: str | None
    include_dirs: list[str]
    include_dirs_auto: bool
    include_dirs_auto_candidates: list[str]
    exclude_dirs: list[str]
    stats_persistent_cache_ttl_sec: float
    delta_full_rebuild_threshold: int
    cache_valkey_url: str
    cache_key_prefix: str | None
    cache_ttl_seconds: str | None


def _normalize_config_value(value: object, *, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized else default


def get_link_graph_default_config_relative_path() -> Path:
    """Resolve default LinkGraph backend config relative path from settings."""
    relative_path = _normalize_config_value(
        get_setting("link_graph.config_relative_path", DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH),
        default=DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH,
    )
    return Path(relative_path)


def normalize_link_graph_dir_entries(raw: object) -> list[str]:
    """Normalize relative directory entries from settings-like values."""
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(item) for item in raw]
    else:
        candidates = []

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = str(candidate).strip().replace("\\", "/").strip("/")
        if not value or value == ".":
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(value)
    return result


def resolve_link_graph_include_dirs(
    include_dirs_raw: object,
    *,
    notebook_root: str | Path | None,
    include_dirs_auto: bool,
    auto_candidates_raw: object,
) -> list[str]:
    """Resolve final LinkGraph include directories from settings inputs."""
    explicit = normalize_link_graph_dir_entries(include_dirs_raw)
    if explicit:
        return explicit

    if not include_dirs_auto:
        return []

    if notebook_root is None:
        return []

    root_path = Path(notebook_root).expanduser()
    if not root_path.exists() or not root_path.is_dir():
        return []

    candidates = normalize_link_graph_dir_entries(auto_candidates_raw)
    if not candidates:
        return []

    resolved: list[str] = []
    for candidate in candidates:
        if (root_path / candidate).is_dir():
            resolved.append(candidate)
    return resolved


def get_link_graph_include_dirs(
    notebook_root: str | Path | None,
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> list[str]:
    """Resolve LinkGraph include dirs from settings + notebook root."""
    reader = setting_reader or get_setting
    include_dirs_raw = reader("link_graph.include_dirs", [])
    include_dirs_auto = _coerce_bool(reader("link_graph.include_dirs_auto", True), default=True)
    auto_candidates_raw = reader("link_graph.include_dirs_auto_candidates", [])
    return resolve_link_graph_include_dirs(
        include_dirs_raw,
        notebook_root=notebook_root,
        include_dirs_auto=include_dirs_auto,
        auto_candidates_raw=auto_candidates_raw,
    )


def resolve_link_graph_excluded_dirs(raw: object) -> list[str]:
    """Resolve final LinkGraph excludes from configured additional entries.

    Hidden/runtime excludes are always enforced. Config entries starting with "."
    are ignored as redundant policy.
    """
    configured = [
        entry for entry in normalize_link_graph_dir_entries(raw) if not entry.startswith(".")
    ]

    merged = list(DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS)
    seen = {item.lower() for item in merged}
    for entry in configured:
        lowered = entry.lower()
        if lowered in seen:
            continue
        merged.append(entry)
        seen.add(lowered)
    return merged


def get_link_graph_excluded_dirs(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> list[str]:
    """Resolve LinkGraph excluded directories from settings + built-in policy."""
    reader = setting_reader or get_setting
    raw = reader(
        "link_graph.exclude_dirs",
        list(DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS),
    )
    return resolve_link_graph_excluded_dirs(raw)


def _first_non_empty(values: list[object]) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_non_negative_float(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
        if not math.isfinite(parsed):
            return default
        return max(0.0, parsed)
    except (TypeError, ValueError):
        return default


def _coerce_int_min(value: object, *, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _coerce_float_bounded(
    value: object,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
        if not math.isfinite(parsed):
            parsed = default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_int_bounded(
    value: object,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def get_link_graph_backend_name(
    name: str | None = None,
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> str:
    """Resolve LinkGraph backend name from explicit value or settings."""
    reader = setting_reader or get_setting
    raw = (name or str(reader("link_graph.backend", DEFAULT_LINK_GRAPH_BACKEND))).strip().lower()
    if raw == DEFAULT_LINK_GRAPH_BACKEND:
        return raw
    raise ValueError(f"Unsupported link_graph backend: {raw or '<empty>'}")


def get_link_graph_root_dir(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> str | None:
    """Resolve configured LinkGraph notebook root dir."""
    reader = setting_reader or get_setting
    return _first_non_empty([reader("link_graph.root_dir", None)])


def get_link_graph_retrieval_mode(
    mode: str | None = None,
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> str:
    """Resolve LinkGraph retrieval mode raw value."""
    reader = setting_reader or get_setting
    return str(
        mode or reader("link_graph.retrieval_mode", DEFAULT_LINK_GRAPH_RETRIEVAL_MODE)
    ).strip()


def get_link_graph_candidate_multiplier(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph candidate multiplier."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.candidate_multiplier", DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER),
        default=DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER,
        minimum=1,
        maximum=20,
    )


def get_link_graph_max_sources(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph max source hints."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.max_sources", DEFAULT_LINK_GRAPH_MAX_SOURCES),
        default=DEFAULT_LINK_GRAPH_MAX_SOURCES,
        minimum=1,
        maximum=100,
    )


def get_link_graph_hybrid_min_hits(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph hybrid minimum graph hits."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.hybrid.min_hits", DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS),
        default=DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS,
        minimum=1,
        maximum=50,
    )


def get_link_graph_hybrid_min_top_score(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph hybrid minimum top score."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader("link_graph.hybrid.min_top_score", DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE),
        default=DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE,
        minimum=0.0,
        maximum=1.0,
    )


def get_link_graph_graph_rows_per_source(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph graph rows per source."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.graph_rows_per_source", DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE),
        default=DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE,
        minimum=1,
        maximum=100,
    )


def get_link_graph_policy_cache_ttl_seconds(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph policy cache TTL seconds."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader("link_graph.policy_cache_ttl_seconds", DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS),
        default=DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS,
        minimum=0.0,
        maximum=600.0,
    )


def get_link_graph_policy_search_timeout_scale(
    query_bucket: str,
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph policy search-timeout scale by query bucket."""
    bucket = str(query_bucket or "").strip().lower()
    if bucket == "machine_like":
        key = "link_graph.policy.search_timeout_scale.machine_like"
        default = DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_MACHINE_LIKE
    elif bucket == "symbol_heavy":
        key = "link_graph.policy.search_timeout_scale.symbol_heavy"
        default = DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SYMBOL_HEAVY
    elif bucket == "short":
        key = "link_graph.policy.search_timeout_scale.short"
        default = DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SHORT
    elif bucket == "long_natural":
        key = "link_graph.policy.search_timeout_scale.long_natural"
        default = DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_LONG_NATURAL
    else:
        key = "link_graph.policy.search_timeout_scale.default"
        default = DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_DEFAULT
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader(key, default),
        default=default,
        minimum=0.05,
        maximum=2.0,
    )


def get_link_graph_policy_search_timeout_seconds(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph policy search timeout seconds."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader(
            "link_graph.policy.search_timeout_seconds",
            DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SECONDS,
        ),
        default=DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SECONDS,
        minimum=0.05,
        maximum=30.0,
    )


def get_link_graph_policy_timeout_marker_ttl_seconds(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph policy timeout-marker TTL seconds."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader(
            "link_graph.policy.timeout_marker_ttl_seconds",
            DEFAULT_LINK_GRAPH_POLICY_TIMEOUT_MARKER_TTL_SECONDS,
        ),
        default=DEFAULT_LINK_GRAPH_POLICY_TIMEOUT_MARKER_TTL_SECONDS,
        minimum=0.0,
        maximum=120.0,
    )


def get_link_graph_proximity_max_stems(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph proximity max stems."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.proximity.max_stems", DEFAULT_LINK_GRAPH_PROXIMITY_MAX_STEMS),
        default=DEFAULT_LINK_GRAPH_PROXIMITY_MAX_STEMS,
        minimum=1,
        maximum=64,
    )


def get_link_graph_proximity_stem_cache_ttl_seconds(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph proximity stem-cache TTL seconds."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader(
            "link_graph.proximity.stem_cache_ttl_seconds",
            DEFAULT_LINK_GRAPH_PROXIMITY_STEM_CACHE_TTL_SECONDS,
        ),
        default=DEFAULT_LINK_GRAPH_PROXIMITY_STEM_CACHE_TTL_SECONDS,
        minimum=0.0,
        maximum=3600.0,
    )


def get_link_graph_proximity_timeout_seconds(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve LinkGraph proximity timeout seconds."""
    reader = setting_reader or get_setting
    return _coerce_float_bounded(
        reader(
            "link_graph.proximity.timeout_seconds", DEFAULT_LINK_GRAPH_PROXIMITY_TIMEOUT_SECONDS
        ),
        default=DEFAULT_LINK_GRAPH_PROXIMITY_TIMEOUT_SECONDS,
        minimum=0.05,
        maximum=30.0,
    )


def get_link_graph_proximity_max_parallel_stems(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph proximity max parallel stems."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader(
            "link_graph.proximity.max_parallel_stems",
            DEFAULT_LINK_GRAPH_PROXIMITY_MAX_PARALLEL_STEMS,
        ),
        default=DEFAULT_LINK_GRAPH_PROXIMITY_MAX_PARALLEL_STEMS,
        minimum=1,
        maximum=32,
    )


def get_link_graph_proximity_neighbor_limit(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> int:
    """Resolve LinkGraph proximity neighbor limit."""
    reader = setting_reader or get_setting
    return _coerce_int_bounded(
        reader("link_graph.proximity.neighbor_limit", DEFAULT_LINK_GRAPH_PROXIMITY_NEIGHBOR_LIMIT),
        default=DEFAULT_LINK_GRAPH_PROXIMITY_NEIGHBOR_LIMIT,
        minimum=0,
        maximum=200,
    )


def get_link_graph_stats_cache_ttl_sec(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve stats cache TTL seconds."""
    reader = setting_reader or get_setting
    return _coerce_non_negative_float(
        reader("link_graph.stats_cache_ttl_sec", DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC),
        default=DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC,
    )


def get_link_graph_stats_timeout_sec(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve stats request timeout seconds."""
    reader = setting_reader or get_setting
    return _coerce_non_negative_float(
        reader("link_graph.stats_timeout_sec", DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC),
        default=DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC,
    )


def get_link_graph_stats_response_probe_timeout_sec(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve stats response fast-probe timeout seconds."""
    reader = setting_reader or get_setting
    return _coerce_non_negative_float(
        reader(
            "link_graph.stats_response_probe_timeout_sec",
            DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC,
        ),
        default=DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC,
    )


def get_link_graph_stats_response_refresh_timeout_sec(
    *,
    setting_reader: Callable[[str, object], object] | None = None,
) -> float:
    """Resolve stats response refresh timeout seconds."""
    reader = setting_reader or get_setting
    return _coerce_non_negative_float(
        reader(
            "link_graph.stats_response_refresh_timeout_sec",
            DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC,
        ),
        default=DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC,
    )


def get_link_graph_runtime_config(
    *,
    env: Mapping[str, str] | None = None,
    reload_on_missing: bool = True,
    setting_reader: Callable[[str, object], object] | None = None,
    reload_settings: Callable[[], None] | None = None,
) -> LinkGraphRuntimeConfig:
    """Resolve unified LinkGraph runtime config from settings + env."""
    reader = setting_reader or get_setting
    include_dirs = normalize_link_graph_dir_entries(reader("link_graph.include_dirs", []))
    include_dirs_auto = _coerce_bool(
        reader("link_graph.include_dirs_auto", True),
        default=True,
    )
    include_dirs_auto_candidates = normalize_link_graph_dir_entries(
        reader("link_graph.include_dirs_auto_candidates", [])
    )
    exclude_dirs = resolve_link_graph_excluded_dirs(
        reader(
            "link_graph.exclude_dirs",
            list(DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS),
        )
    )
    root_dir = get_link_graph_root_dir(setting_reader=reader)
    stats_persistent_cache_ttl_sec = _coerce_non_negative_float(
        reader(
            "link_graph.stats_persistent_cache_ttl_sec",
            DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC,
        ),
        default=DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC,
    )
    delta_full_rebuild_threshold = _coerce_int_min(
        reader(
            "link_graph.index.delta.full_rebuild_threshold",
            DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD,
        ),
        default=DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD,
        minimum=1,
    )
    cache_valkey_url = get_link_graph_cache_valkey_url(
        env=env,
        reload_on_missing=reload_on_missing,
        setting_reader=reader,
        reload_settings=reload_settings,
    )
    cache_key_prefix = get_link_graph_cache_key_prefix(
        env=env,
        setting_reader=reader,
    )
    cache_ttl_seconds = get_link_graph_cache_ttl_seconds(
        env=env,
        setting_reader=reader,
    )
    return LinkGraphRuntimeConfig(
        root_dir=root_dir,
        include_dirs=include_dirs,
        include_dirs_auto=include_dirs_auto,
        include_dirs_auto_candidates=include_dirs_auto_candidates,
        exclude_dirs=exclude_dirs,
        stats_persistent_cache_ttl_sec=stats_persistent_cache_ttl_sec,
        delta_full_rebuild_threshold=delta_full_rebuild_threshold,
        cache_valkey_url=cache_valkey_url,
        cache_key_prefix=cache_key_prefix,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def resolve_link_graph_cache_valkey_url(
    *,
    env: Mapping[str, str] | None = None,
    setting_value: object = None,
) -> str:
    """Resolve LinkGraph cache Valkey URL from config-first unified source."""
    env_map = env if env is not None else os.environ
    resolved = _first_non_empty(
        [
            setting_value,
            env_map.get(LINK_GRAPH_CACHE_VALKEY_URL_ENV),
        ]
    )
    if resolved:
        return resolved
    raise RuntimeError(
        "link_graph cache valkey url is required "
        f"(set {LINK_GRAPH_CACHE_VALKEY_URL_ENV} or link_graph.cache.valkey_url)"
    )


def get_link_graph_cache_valkey_url(
    *,
    env: Mapping[str, str] | None = None,
    reload_on_missing: bool = True,
    setting_reader: Callable[[str, object], object] | None = None,
    reload_settings: Callable[[], None] | None = None,
) -> str:
    """Unified config-first resolver for LinkGraph cache Valkey URL.

    Resolution order:
    1) `link_graph.cache.valkey_url` from settings overlays (`wendao.yaml` / user config)
    2) `VALKEY_URL` environment variable

    When `reload_on_missing=True`, settings cache is reloaded once before final failure.
    """
    reader = setting_reader or get_setting
    setting_value = reader("link_graph.cache.valkey_url", None)
    try:
        return resolve_link_graph_cache_valkey_url(env=env, setting_value=setting_value)
    except RuntimeError:
        if not reload_on_missing:
            raise
        if reload_settings is not None:
            with suppress(Exception):
                reload_settings()
        else:
            try:
                from .settings import Settings

                Settings().reload()
            except Exception:
                # Keep original behavior: only best-effort reload.
                pass
        return resolve_link_graph_cache_valkey_url(
            env=env,
            setting_value=reader("link_graph.cache.valkey_url", None),
        )


def get_link_graph_cache_key_prefix(
    *,
    env: Mapping[str, str] | None = None,
    setting_reader: Callable[[str, object], object] | None = None,
) -> str | None:
    """Unified resolver for LinkGraph cache key prefix."""
    reader = setting_reader or get_setting
    return resolve_link_graph_cache_key_prefix(
        env=env,
        setting_value=reader("link_graph.cache.key_prefix", None),
    )


def get_link_graph_cache_ttl_seconds(
    *,
    env: Mapping[str, str] | None = None,
    setting_reader: Callable[[str, object], object] | None = None,
) -> str | None:
    """Unified resolver for LinkGraph cache TTL seconds."""
    reader = setting_reader or get_setting
    return resolve_link_graph_cache_ttl_seconds(
        env=env,
        setting_value=reader("link_graph.cache.ttl_seconds", None),
    )


def resolve_link_graph_cache_key_prefix(
    *,
    env: Mapping[str, str] | None = None,
    setting_value: object = None,
) -> str | None:
    """Resolve LinkGraph cache key prefix with env-over-setting precedence."""
    env_map = env if env is not None else os.environ
    return _first_non_empty([env_map.get(LINK_GRAPH_VALKEY_KEY_PREFIX_ENV), setting_value])


def resolve_link_graph_cache_ttl_seconds(
    *,
    env: Mapping[str, str] | None = None,
    setting_value: object = None,
) -> str | None:
    """Resolve LinkGraph cache TTL with env-over-setting precedence."""
    env_map = env if env is not None else os.environ
    return _first_non_empty([env_map.get(LINK_GRAPH_VALKEY_TTL_SECONDS_ENV), setting_value])


__all__ = [
    "DEFAULT_LINK_GRAPH_BACKEND",
    "DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER",
    "DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH",
    "DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD",
    "DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS",
    "DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS",
    "DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE",
    "DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS",
    "DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE",
    "DEFAULT_LINK_GRAPH_MAX_SOURCES",
    "DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_DEFAULT",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_LONG_NATURAL",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_MACHINE_LIKE",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SHORT",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SCALE_SYMBOL_HEAVY",
    "DEFAULT_LINK_GRAPH_POLICY_SEARCH_TIMEOUT_SECONDS",
    "DEFAULT_LINK_GRAPH_POLICY_TIMEOUT_MARKER_TTL_SECONDS",
    "DEFAULT_LINK_GRAPH_PROXIMITY_MAX_PARALLEL_STEMS",
    "DEFAULT_LINK_GRAPH_PROXIMITY_MAX_STEMS",
    "DEFAULT_LINK_GRAPH_PROXIMITY_NEIGHBOR_LIMIT",
    "DEFAULT_LINK_GRAPH_PROXIMITY_STEM_CACHE_TTL_SECONDS",
    "DEFAULT_LINK_GRAPH_PROXIMITY_TIMEOUT_SECONDS",
    "DEFAULT_LINK_GRAPH_RETRIEVAL_MODE",
    "DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC",
    "DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC",
    "DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC",
    "DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC",
    "DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC",
    "LINK_GRAPH_CACHE_VALKEY_URL_ENV",
    "LINK_GRAPH_VALKEY_KEY_PREFIX_ENV",
    "LINK_GRAPH_VALKEY_TTL_SECONDS_ENV",
    "LinkGraphRuntimeConfig",
    "get_link_graph_backend_name",
    "get_link_graph_cache_key_prefix",
    "get_link_graph_cache_ttl_seconds",
    "get_link_graph_cache_valkey_url",
    "get_link_graph_candidate_multiplier",
    "get_link_graph_default_config_relative_path",
    "get_link_graph_excluded_dirs",
    "get_link_graph_graph_rows_per_source",
    "get_link_graph_hybrid_min_hits",
    "get_link_graph_hybrid_min_top_score",
    "get_link_graph_include_dirs",
    "get_link_graph_max_sources",
    "get_link_graph_policy_cache_ttl_seconds",
    "get_link_graph_policy_search_timeout_scale",
    "get_link_graph_policy_search_timeout_seconds",
    "get_link_graph_policy_timeout_marker_ttl_seconds",
    "get_link_graph_proximity_max_parallel_stems",
    "get_link_graph_proximity_max_stems",
    "get_link_graph_proximity_neighbor_limit",
    "get_link_graph_proximity_stem_cache_ttl_seconds",
    "get_link_graph_proximity_timeout_seconds",
    "get_link_graph_retrieval_mode",
    "get_link_graph_root_dir",
    "get_link_graph_runtime_config",
    "get_link_graph_stats_cache_ttl_sec",
    "get_link_graph_stats_response_probe_timeout_sec",
    "get_link_graph_stats_response_refresh_timeout_sec",
    "get_link_graph_stats_timeout_sec",
    "normalize_link_graph_dir_entries",
    "resolve_link_graph_cache_key_prefix",
    "resolve_link_graph_cache_ttl_seconds",
    "resolve_link_graph_cache_valkey_url",
    "resolve_link_graph_excluded_dirs",
    "resolve_link_graph_include_dirs",
]
