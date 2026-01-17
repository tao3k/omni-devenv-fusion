# config
"""
Configuration Module

Phase 33: Modularized subpackage.

Modules:
- settings.py: Settings class and functions
- directory.py: Configuration directory management

Usage:
    from common.config.settings import get_setting
    from common.config import get_setting  # Backward compatibility
"""

from .settings import (
    Settings,
    get_setting,
    get_config_path,
    has_setting,
    list_setting_sections,
    get_conf_directory,
    set_configuration_directory,
)

from .directory import (
    set_conf_dir,
    get_conf_dir,
)

# Backward compatibility: Re-export everything
__all__ = [
    # From settings
    "Settings",
    "get_setting",
    "get_config_path",
    "has_setting",
    "list_setting_sections",
    "get_conf_directory",
    "set_configuration_directory",
    # From directory
    "set_conf_dir",
    "get_conf_dir",
]
