# settings.py
"""
Project Settings - Configuration File Path Resolution

This module is a backward-compatible wrapper.
New code should import from common.config.settings instead.

Phase 33: Re-exports from common.config subpackage.

Usage:
    # New way (recommended)
    from common.config.settings import get_setting

    # Old way (still works for backward compatibility)
    from common.config.settings import get_setting
"""

from __future__ import annotations

from common.config.settings import (
    Settings,
    get_setting,
    get_config_path,
    has_setting,
    list_setting_sections,
    get_conf_directory,
    set_configuration_directory,
)

from common.config.directory import (
    set_conf_dir,
    get_conf_dir,
)

from common.config.commits import (
    get_commit_types,
    get_commit_scopes,
    get_commit_protocol,
)

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
