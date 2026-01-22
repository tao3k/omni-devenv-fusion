# config
"""
Configuration Module

Modularized subpackage.

Modules:
- dirs.py: Physical directory management (Layer 0)
- paths.py: Semantic path resolution (Layer 1)
- settings.py: Settings class and functions

Usage:
    from omni.foundation.config.settings import get_setting
    from omni.foundation.config import get_setting  # Backward compatibility
"""

from .dirs import (
    PRJ_DIRS,
    PRJ_CONFIG,
    PRJ_RUNTIME,
    PRJ_DATA,
    PRJ_CACHE,
    get_config_dir,
)
from .settings import (
    Settings,
    get_setting,
    get_settings,
)
from .paths import (
    ConfigPaths,
    get_config_paths,
)


# Create backward-compatible stubs
def get_conf_directory() -> str:
    """Get the configuration directory (legacy wrapper)."""
    return str(PRJ_DIRS.config_home)


def set_configuration_directory(path: str) -> None:
    """Set the configuration directory (legacy wrapper)."""
    import os

    os.environ["PRJ_CONFIG_HOME"] = path


def get_config_path(key: str) -> str:
    """Get a configuration file path (legacy wrapper)."""
    settings = Settings()
    return settings.get(key, "")


def has_setting(key: str) -> bool:
    """Check if a setting exists (legacy wrapper)."""
    return Settings().get(key) is not None


def list_setting_sections() -> list[str]:
    """List all settings sections (legacy wrapper)."""
    settings = Settings()
    return settings.list_sections()


__all__ = [
    # From dirs (Layer 0)
    "PRJ_DIRS",
    "PRJ_CONFIG",
    "PRJ_RUNTIME",
    "PRJ_DATA",
    "PRJ_CACHE",
    "get_config_dir",
    # From settings
    "Settings",
    "get_setting",
    "get_settings",
    # From paths (Layer 1)
    "ConfigPaths",
    "get_config_paths",
    # Legacy compatibility
    "get_conf_directory",
    "set_configuration_directory",
    "get_config_path",
    "has_setting",
    "list_setting_sections",
]
