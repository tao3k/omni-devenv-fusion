"""Runtime config helpers for the standalone xiuxian-wendao backend."""

from __future__ import annotations

import os
from pathlib import Path

from ..models import (
    DEFAULT_EXCLUDED_ADDITIONAL_DIRS,
    DEFAULT_EXCLUDED_HIDDEN_DIRS,
    LINK_GRAPH_CACHE_VALKEY_URL_ENV,
    LINK_GRAPH_VALKEY_KEY_PREFIX_ENV,
    LINK_GRAPH_VALKEY_TTL_SECONDS_ENV,
    WendaoRuntimeConfig,
)


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def normalize_dir_entries(raw: object) -> list[str]:
    """Normalize configured relative directory entries."""
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


def resolve_include_dirs(
    include_dirs_raw: object,
    *,
    notebook_root: str | Path | None,
    include_dirs_auto: bool,
    auto_candidates_raw: object,
) -> list[str]:
    """Resolve final include dirs from explicit and auto settings."""
    explicit = normalize_dir_entries(include_dirs_raw)
    if explicit:
        return explicit

    if not include_dirs_auto:
        return []

    if notebook_root is None:
        return []

    root_path = Path(notebook_root).expanduser()
    if not root_path.exists() or not root_path.is_dir():
        return []

    candidates = normalize_dir_entries(auto_candidates_raw)
    if not candidates:
        return []

    resolved: list[str] = []
    for candidate in candidates:
        if (root_path / candidate).is_dir():
            resolved.append(candidate)
    return resolved


def resolve_excluded_dirs(raw: object) -> list[str]:
    """Resolve excluded dirs, enforcing hidden/runtime defaults."""
    configured = [entry for entry in normalize_dir_entries(raw) if not entry.startswith(".")]

    merged = list(DEFAULT_EXCLUDED_HIDDEN_DIRS)
    seen = {item.lower() for item in merged}
    for entry in configured:
        lowered = entry.lower()
        if lowered in seen:
            continue
        merged.append(entry)
        seen.add(lowered)
    return merged


def default_runtime_config_from_env() -> WendaoRuntimeConfig:
    """Build a standalone runtime config from environment variables."""
    root_dir = str(os.getenv("LINK_GRAPH_ROOT_DIR") or "").strip() or None
    include_dirs = normalize_dir_entries(os.getenv("LINK_GRAPH_INCLUDE_DIRS", ""))
    include_dirs_auto = _coerce_bool(
        os.getenv("LINK_GRAPH_INCLUDE_DIRS_AUTO", "false"), default=False
    )
    include_dirs_auto_candidates = normalize_dir_entries(
        os.getenv("LINK_GRAPH_INCLUDE_DIRS_AUTO_CANDIDATES", "")
    )
    exclude_raw = normalize_dir_entries(",".join(DEFAULT_EXCLUDED_ADDITIONAL_DIRS))
    exclude_dirs = resolve_excluded_dirs(exclude_raw)

    cache_valkey_url = str(os.getenv(LINK_GRAPH_CACHE_VALKEY_URL_ENV, "") or "").strip()
    cache_key_prefix = str(os.getenv(LINK_GRAPH_VALKEY_KEY_PREFIX_ENV, "") or "").strip() or None
    cache_ttl = str(os.getenv(LINK_GRAPH_VALKEY_TTL_SECONDS_ENV, "") or "").strip() or None

    return WendaoRuntimeConfig(
        root_dir=root_dir,
        include_dirs=include_dirs,
        include_dirs_auto=include_dirs_auto,
        include_dirs_auto_candidates=include_dirs_auto_candidates,
        exclude_dirs=exclude_dirs,
        stats_persistent_cache_ttl_sec=120.0,
        delta_full_rebuild_threshold=256,
        cache_valkey_url=cache_valkey_url,
        cache_key_prefix=cache_key_prefix,
        cache_ttl_seconds=cache_ttl,
    )


__all__ = [
    "default_runtime_config_from_env",
    "normalize_dir_entries",
    "resolve_excluded_dirs",
    "resolve_include_dirs",
]
