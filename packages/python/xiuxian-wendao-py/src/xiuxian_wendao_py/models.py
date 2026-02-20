"""Data models for the xiuxian-wendao Python backend core."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_EXCLUDED_HIDDEN_DIRS: tuple[str, ...] = (
    ".git",
    ".cache",
    ".devenv",
    ".run",
    ".venv",
)
DEFAULT_EXCLUDED_ADDITIONAL_DIRS: tuple[str, ...] = (
    "target",
    "node_modules",
)

LINK_GRAPH_CACHE_VALKEY_URL_ENV: str = "VALKEY_URL"
LINK_GRAPH_VALKEY_KEY_PREFIX_ENV: str = "OMNI_LINK_GRAPH_VALKEY_KEY_PREFIX"
LINK_GRAPH_VALKEY_TTL_SECONDS_ENV: str = "OMNI_LINK_GRAPH_VALKEY_TTL_SECONDS"
LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION: str = "omni.link_graph.valkey_cache_snapshot.v1"
LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION: str = "omni.link_graph.stats.cache.v1"


@dataclass(frozen=True, slots=True)
class WendaoRuntimeConfig:
    """Runtime config consumed by the standalone backend core."""

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


__all__ = [
    "DEFAULT_EXCLUDED_ADDITIONAL_DIRS",
    "DEFAULT_EXCLUDED_HIDDEN_DIRS",
    "LINK_GRAPH_CACHE_VALKEY_URL_ENV",
    "LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION",
    "LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION",
    "LINK_GRAPH_VALKEY_KEY_PREFIX_ENV",
    "LINK_GRAPH_VALKEY_TTL_SECONDS_ENV",
    "WendaoRuntimeConfig",
]
