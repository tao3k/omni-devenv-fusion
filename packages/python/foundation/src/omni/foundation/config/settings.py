"""
Project Settings - Configuration Manager (Refactored)

Architecture:
- Layer 0 (Base): <git-root>/assets/settings.yaml (System Defaults)
- Layer 1 (User): $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml (User Overrides)
- Control: CLI flag `--conf` sets $PRJ_CONFIG_HOME dynamically.

The final configuration is a deep merge of User Overrides onto System Defaults.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any

# Layer 0: Physical Directory Management
from .dirs import PRJ_CONFIG, PRJ_DIRS

# YAML support
try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class Settings:
    """
    Unified Settings Manager.

    Logic:
    1. Parse `--conf` flag -> updates PRJ_CONFIG_HOME.
    2. Load `<git-root>/assets/settings.yaml` (Defaults).
    3. Load `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` (User).
    4. Merge User > Defaults.
    """

    _instance: Settings | None = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls) -> Settings:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize settings instance.

        Note: _data is only initialized once to preserve loaded settings
        across multiple Settings() calls (Python calls __init__ each time).
        """
        if not hasattr(self, "_data"):
            self._data: dict[str, Any] = {}

    def _ensure_loaded(self) -> None:
        """Ensure settings are loaded (Thread-Safe)."""
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._load()
                    self._loaded = True

    def _parse_cli_conf(self) -> str | None:
        """
        Extract --conf argument from sys.argv manually.
        We do this here to avoid conflicts with downstream argparse logic.
        """
        args = sys.argv
        for i, arg in enumerate(args):
            if arg == "--conf" and i + 1 < len(args):
                return args[i + 1]
            if arg.startswith("--conf="):
                return arg.split("=", 1)[1]
        return None

    def _load(self) -> None:
        """Execute the Dual-Layer Loading Strategy."""
        # Always refresh PRJ_DIRS cache before resolving config paths.
        # This guarantees path consistency when tests or callers modify
        # PRJ_CONFIG_HOME dynamically between Settings reloads.
        PRJ_DIRS.clear_cache()

        # 1. CLI override fallback: if --conf is explicitly provided in argv,
        # it takes precedence for this process.
        # Primary ownership still lives in CLI bootstrap (app.py), but this
        # keeps Settings deterministic in direct/test invocation paths.
        cli_conf_dir = self._parse_cli_conf()
        if cli_conf_dir:
            # Dynamically update the Environment Layer
            os.environ["PRJ_CONFIG_HOME"] = cli_conf_dir
            # Clear again after --conf mutation to ensure fresh path resolution.
            PRJ_DIRS.clear_cache()

        # 2. Load Base Defaults (from <git-root>/assets/settings.yaml)
        # This serves as the "Interface Definition" or "Factory Defaults"
        defaults = {}
        project_root = PRJ_DIRS.config_home.parent
        assets_settings = project_root / "assets" / "settings.yaml"

        if assets_settings.exists():
            defaults = self._read_yaml(assets_settings)

        # 3. Load User Config (from $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml)
        # This is where the user's specific customizations live
        user_config = {}
        user_settings_path = PRJ_CONFIG("omni-dev-fusion", "settings.yaml")

        if user_settings_path.exists():
            user_config = self._read_yaml(user_settings_path)

        # 4. Merge: User overrides Defaults
        self._data = self._deep_merge(defaults, user_config)

    def _read_yaml(self, path: os.PathLike) -> dict[str, Any]:
        """Helper to read YAML safely."""
        from pathlib import Path

        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8")
            if _YAML_AVAILABLE:
                return yaml.safe_load(content) or {}  # type: ignore[union-attr]
            else:
                return self._parse_simple_yaml(content)
        except Exception:
            return {}

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """
        Recursive deep merge of two dictionaries.
        Override values replace base values.
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _parse_simple_yaml(self, content: str) -> dict[str, Any]:
        """Fallback YAML parser."""
        result: dict[str, Any] = {}
        current_section: dict[str, Any] | None = None

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.endswith(":") and not line.startswith("-"):
                section_name = line[:-1].strip()
                result[section_name] = {}
                current_section = result[section_name]
            elif ":" in line and current_section is not None:
                key, value = line.split(":", 1)
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    value = [v.strip().strip('"') for v in value[1:-1].split(",")]
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                current_section[key.strip()] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'api.key')."""
        self._ensure_loaded()
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def reload(self) -> None:
        """Force reload settings."""
        with self._instance_lock:
            self._loaded = False
            self._load()
            self._loaded = True

    def list_sections(self) -> list[str]:
        """List all settings sections."""
        self._ensure_loaded()
        return list(self._data.keys())

    def get_path(self, key: str) -> str:
        """Get a path setting value."""
        result = self.get(key)
        return result if result else ""

    def get_list(self, key: str) -> list[str]:
        """Get a list setting value."""
        result = self.get(key)
        return result if isinstance(result, list) else []

    def has_setting(self, key: str) -> bool:
        """Check if a setting exists."""
        return self.get(key) is not None

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire settings section."""
        self._ensure_loaded()
        return self._data.get(section, {})

    @property
    def conf_dir(self) -> str:
        """Get the active application configuration directory path."""
        from .dirs import PRJ_CONFIG

        return str(PRJ_CONFIG("omni-dev-fusion"))


def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value directly."""
    return Settings().get(key, default)


def get_settings() -> Settings:
    """Get the Settings singleton (Useful for DI)."""
    return Settings()


__all__ = [
    "Settings",
    "get_setting",
    "get_settings",
]
