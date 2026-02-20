"""Backend factory for common link-graph engine."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from omni.foundation.config.link_graph_runtime import (
    get_link_graph_backend_name,
    get_link_graph_root_dir,
)
from omni.foundation.config.settings import get_setting

from .wendao_backend import WendaoLinkGraphBackend

if TYPE_CHECKING:
    from .backend import LinkGraphBackend

_BACKEND_CACHE: dict[tuple[str, str], LinkGraphBackend] = {}


def _resolve_backend_name(name: str | None = None) -> str:
    return get_link_graph_backend_name(name, setting_reader=get_setting)


def _resolve_notebook_dir(notebook_dir: str | Path | None = None) -> str | None:
    if notebook_dir is not None:
        return str(Path(notebook_dir).expanduser().resolve())
    raw = get_link_graph_root_dir(setting_reader=get_setting)
    if raw:
        return str(Path(str(raw)).expanduser().resolve())
    return None


def _build_backend(backend_name: str, notebook_dir: str | None) -> LinkGraphBackend:
    if backend_name == "wendao":
        return WendaoLinkGraphBackend(notebook_dir)
    raise ValueError(f"Unsupported link_graph backend: {backend_name}")


def _cache_key(backend_name: str, notebook_dir: str | None) -> tuple[str, str]:
    return backend_name, notebook_dir or ""


def get_link_graph_backend(
    *,
    backend_name: str | None = None,
    notebook_dir: str | Path | None = None,
    use_cache: bool = True,
) -> LinkGraphBackend:
    """Get backend instance by configured backend + notebook root."""
    resolved_name = _resolve_backend_name(backend_name)
    resolved_dir = _resolve_notebook_dir(notebook_dir)
    if not use_cache:
        return _build_backend(resolved_name, resolved_dir)

    key = _cache_key(resolved_name, resolved_dir)
    cached = _BACKEND_CACHE.get(key)
    if cached is not None:
        return cached

    built = _build_backend(resolved_name, resolved_dir)
    _BACKEND_CACHE[key] = built
    return built


def reset_link_graph_backend_cache() -> None:
    """Reset process-local backend cache."""
    _BACKEND_CACHE.clear()
    return None


__all__ = [
    "get_link_graph_backend",
    "reset_link_graph_backend_cache",
]
