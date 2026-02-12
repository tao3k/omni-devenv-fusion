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
        Path to the zk notebook directory (default: assets/knowledge)

    Usage:
        >>> from omni.foundation.config.zk import get_zk_notebook_dir
        >>> zk_dir = get_zk_notebook_dir()
        >>> # Returns: /project/assets/knowledge
    """
    from omni.foundation.services.reference import get_reference_path

    notebook = get_reference_path("zk.notebook", fallback="assets/knowledge")
    # If notebook is a relative path, resolve from project root
    if not Path(notebook).is_absolute():
        from omni.foundation.runtime.gitops import get_project_root

        notebook = str(get_project_root() / notebook)
    return Path(notebook)


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
