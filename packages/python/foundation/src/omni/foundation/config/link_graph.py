"""LinkGraph notebook utilities.

Resolves LinkGraph notebook paths from references and settings.
"""

from __future__ import annotations

from pathlib import Path

from .link_graph_runtime import get_link_graph_default_config_relative_path


def _is_configured_path(value: Path) -> bool:
    return str(value) not in {"", "."}


def get_link_graph_notebook_dir() -> Path:
    """Get the LinkGraph notebook directory path."""
    from omni.foundation.services.reference import ref

    value = ref("link_graph.notebook")
    return value if _is_configured_path(value) else Path()


def get_link_graph_config_path() -> Path:
    """Get the LinkGraph backend config file path."""
    notebook_dir = get_link_graph_notebook_dir()
    return notebook_dir / get_link_graph_default_config_relative_path()


def get_link_graph_harvested_dir() -> Path:
    """Get harvested reports directory used by LinkGraph indexing."""
    from omni.foundation.services.reference import ref

    value = ref("link_graph.harvested")
    return value if _is_configured_path(value) else Path()


__all__ = [
    "get_link_graph_config_path",
    "get_link_graph_harvested_dir",
    "get_link_graph_notebook_dir",
]
