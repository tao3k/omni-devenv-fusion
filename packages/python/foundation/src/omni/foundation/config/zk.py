# zk.py
"""
Zettelkasten (zk) Notebook Utilities.

Manages zk notebook configuration from references.yaml.

Usage:
    >>> from omni.foundation.config.zk import get_zk_notebook_dir
    >>> zk_dir = get_zk_notebook_dir()
    >>> # Returns: /project/assets/knowledge
"""

from pathlib import Path


def get_zk_notebook_dir() -> Path:
    """Get the zk notebook directory path.

    Reads from references.yaml -> zk.notebook

    Returns:
        Path to the zk notebook directory (from references.yaml zk.notebook)

    Usage:
        >>> from omni.foundation.config.zk import get_zk_notebook_dir
        >>> zk_dir = get_zk_notebook_dir()
        >>> # Returns: /project/assets/knowledge
    """
    from omni.foundation.services.reference import ref

    p = ref("zk.notebook")
    return p if str(p) else Path()


def get_zk_config_path() -> Path:
    """Get the zk configuration file path.

    Reads from references.yaml -> zk.config

    Returns:
        Path to zk.toml file

    Usage:
        >>> from omni.foundation.config.zk import get_zk_config_path
        >>> zk_config = get_zk_config_path()
        >>> # Returns: /project/assets/knowledge/.zk/zk.toml
    """
    # Get the notebook directory (already resolved)
    notebook_dir = get_zk_notebook_dir()
    return notebook_dir / ".zk" / "zk.toml"


__all__ = [
    "get_zk_notebook_dir",
    "get_zk_config_path",
]
