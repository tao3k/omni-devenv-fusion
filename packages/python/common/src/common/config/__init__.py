# config
"""
Configuration Module

Phase 33: Modularized subpackage.

Modules:
- settings.py: Settings class and functions
- directory.py: Configuration directory management
- commits.py: Commit-related configuration

Usage:
    # New modular imports (recommended)
    from common.config.settings import get_setting
    from common.config.commits import get_commit_types

    # Old imports (still work for backward compatibility)
    from common.config.settings import get_setting
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

from .commits import (
    get_commit_types,
    get_commit_scopes,
    get_commit_protocol,
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
    # From commits
    "get_commit_types",
    "get_commit_scopes",
    "get_commit_protocol",
]
