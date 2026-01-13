# config/settings.py
"""
Project Settings - Configuration File Path Resolution

Provides unified API for reading configuration file paths from settings.yaml.
Supports --conf flag for custom configuration directory.

Phase 33: Modularized from settings.py

Features:
- Reads from settings.yaml in conf directory
- Supports --conf flag for custom configuration path
- Dot-notation access (e.g., "config.cog_toml")
- Thread-safe singleton pattern
- Hot reload support

Usage:
    # Default (uses assets/ directory)
    from common.config.settings import get_setting
    cog_path = get_setting("config.cog_toml")  # Returns: "cog.toml"

    # Custom configuration directory
    python script.py --conf /path/to/conf
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from common.gitops import get_project_root

# YAML support (try PyYAML first, fallback to simple parsing)
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .directory import get_conf_dir


class Settings:
    """
    Project Settings - Singleton for configuration file paths.

    Reads from settings.yaml in the configuration directory.

    Usage:
        settings = Settings()
        cog_path = settings.get("config.cog_toml")  # Returns: "cog.toml"
    """

    _instance: Optional["Settings"] = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls, conf_dir: str | None = None) -> "Settings":
        """Create singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data: dict[str, Any] = {}
                    cls._instance._conf_dir: str | None = conf_dir
        return cls._instance

    def __init__(self, conf_dir: str | None = None) -> None:
        """Initialize settings."""
        pass

    def _ensure_loaded(self) -> None:
        """Ensure settings are loaded, thread-safe with double-check locking."""
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._load()
                    self._loaded = True

    def _load(self) -> None:
        """Load settings from settings.yaml."""
        # Determine config directory
        if self._conf_dir is not None:
            conf_dir = self._conf_dir
        else:
            conf_dir = get_conf_dir()

        project_root = get_project_root()
        settings_path = project_root / conf_dir / "settings.yaml"

        if not settings_path.exists():
            self._data = {}
            return

        try:
            content = settings_path.read_text(encoding="utf-8")
            if YAML_AVAILABLE:
                self._data = yaml.safe_load(content) or {}
            else:
                self._data = self._parse_simple_yaml(content)
        except Exception:
            self._data = {}

    def _parse_simple_yaml(self, content: str) -> dict[str, Any]:
        """Simple YAML parser for basic key-value structure."""
        result: dict[str, Any] = {}
        current_section: dict[str, Any] | None = None

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check for section header (ends with colon)
            if line.endswith(":") and not line.startswith("-"):
                section_name = line[:-1].strip()
                result[section_name] = {}
                current_section = result[section_name]
            elif ":" in line and current_section is not None:
                key, value = line.split(":", 1)
                value = value.strip()
                # Handle list values
                if value.startswith("[") and value.endswith("]"):
                    value = [v.strip().strip('"') for v in value[1:-1].split(",")]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                current_section[key.strip()] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value using dot notation.

        Args:
            key: Dot-separated path (e.g., "config.cog_toml")
            default: Default value if key not found

        Returns:
            The setting value or default
        """
        self._ensure_loaded()

        keys = key.split(".")
        value = self._data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_path(self, key: str) -> str:
        """
        Get a path setting value.

        Args:
            key: Dot-separated path (e.g., "config.cog_toml")

        Returns:
            Path string, or empty string if not found
        """
        result = self.get(key)
        return result if result else ""

    def get_list(self, key: str) -> list[str]:
        """
        Get a list setting value.

        Args:
            key: Dot-separated path (e.g., "commit.types")

        Returns:
            List of strings, or empty list if not found
        """
        result = self.get(key)
        return result if isinstance(result, list) else []

    def has_setting(self, key: str) -> bool:
        """
        Check if a setting exists.

        Args:
            key: Dot-separated path to check

        Returns:
            True if setting exists, False otherwise
        """
        return self.get(key) is not None

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get an entire settings section.

        Args:
            section: Section name (e.g., "config")

        Returns:
            Section dictionary or empty dict
        """
        self._ensure_loaded()
        return self._data.get(section, {})

    def list_sections(self) -> list[str]:
        """
        List all settings sections.

        Returns:
            List of section names
        """
        self._ensure_loaded()
        return list(self._data.keys())

    def reload(self) -> None:
        """Force reload settings from YAML file."""
        with self._instance_lock:
            self._loaded = False
            self._ensure_loaded()

    @property
    def is_loaded(self) -> bool:
        """Check if settings have been loaded."""
        return self._loaded

    @property
    def conf_dir(self) -> str:
        """Get the configuration directory."""
        if self._conf_dir is not None:
            return self._conf_dir
        return get_conf_dir()


# =============================================================================
# Convenience Functions
# =============================================================================


def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a setting value.

    Args:
        key: Dot-separated path (e.g., "config.cog_toml")
        default: Default value if key not found

    Returns:
        The setting value or default. Path values are auto-resolved with project_root.
    """
    settings = Settings()
    value = settings.get(key, default)

    # Auto-resolve path values with project_root (SSOT)
    # Skip URLs (http://, https://, etc.)
    if (
        isinstance(value, str)
        and value
        and not value.startswith(("http://", "https://", "file://"))
        and (
            value.endswith((".yaml", ".yml", ".toml", ".json", ".nix"))
            or "/" in value
            or value.startswith("../")
        )
    ):
        from common.gitops import get_project_root

        project_root = get_project_root()
        return str(project_root / value)

    return value


def get_config_path(key: str) -> str:
    """
    Get a configuration file path.

    Args:
        key: Dot-separated path (e.g., "config.cog_toml")

    Returns:
        Path string
    """
    settings = Settings()
    return settings.get_path(key)


def has_setting(key: str) -> bool:
    """Check if a setting exists."""
    settings = Settings()
    return settings.has_setting(key)


def list_setting_sections() -> list[str]:
    """List all settings sections."""
    settings = Settings()
    return settings.list_sections()


def get_conf_directory() -> str:
    """Get the current configuration directory."""
    return get_conf_dir()


def set_configuration_directory(path: str) -> None:
    """Set the configuration directory."""
    from .directory import set_conf_dir

    set_conf_dir(path)


__all__ = [
    "Settings",
    "get_setting",
    "get_config_path",
    "has_setting",
    "list_setting_sections",
    "get_conf_directory",
    "set_configuration_directory",
]
