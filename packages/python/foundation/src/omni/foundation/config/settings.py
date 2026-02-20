"""
Project Settings - Configuration Manager (Refactored)

Architecture (two-layer config with modular files):
- System:
  - <git-root>/packages/conf/settings.yaml (general defaults)
  - <git-root>/packages/conf/wendao.yaml (LinkGraph/Wendao defaults)
- User:
  - $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml (general overrides)
  - $PRJ_CONFIG_HOME/omni-dev-fusion/wendao.yaml (LinkGraph/Wendao overrides)
- CLI flag `--conf` can set PRJ_CONFIG_HOME for a run.

get_setting() returns merged effective values. User layer overrides system layer;
for LinkGraph keys, `wendao.yaml` overlays `settings.yaml` at each layer.
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
    2. Load system defaults:
       - `<git-root>/packages/conf/settings.yaml`
       - `<git-root>/packages/conf/wendao.yaml` (overlays settings defaults)
    3. Load user overrides:
       - `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml`
       - `$PRJ_CONFIG_HOME/omni-dev-fusion/wendao.yaml` (overlays user settings)
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

        # 2. Load system defaults from packages/conf/*.yaml
        defaults = {}
        try:
            from omni.foundation.runtime.gitops import get_project_root

            project_root = get_project_root()
        except Exception:
            project_root = PRJ_DIRS.config_home.parent
        conf_dir = project_root / "packages" / "conf"
        system_settings = conf_dir / "settings.yaml"
        if system_settings.exists():
            defaults = self._read_yaml(system_settings)

        # 2b. Load LinkGraph/Wendao defaults from separate config file.
        # This overlays system settings for `link_graph.*` and related keys.
        system_wendao = conf_dir / "wendao.yaml"
        if system_wendao.exists():
            defaults = self._deep_merge(defaults, self._read_yaml(system_wendao))

        # 2c. Load skills from packages/conf/skills.yaml (convention: same dir as settings.yaml)
        skills_path = conf_dir / "skills.yaml"
        defaults["skills"] = self._read_yaml(skills_path) if skills_path.exists() else {}

        # 3. Load user config overlays from $PRJ_CONFIG_HOME/omni-dev-fusion/*.yaml
        user_config = {}
        user_settings_path = PRJ_CONFIG("omni-dev-fusion", "settings.yaml")
        if user_settings_path.exists():
            user_config = self._read_yaml(user_settings_path)

        user_wendao = {}
        user_wendao_path = PRJ_CONFIG("omni-dev-fusion", "wendao.yaml")
        if user_wendao_path.exists():
            user_wendao = self._read_yaml(user_wendao_path)

        # 4. Merge: User overrides Defaults.
        # For link_graph.* keys, user wendao.yaml is the highest-priority user layer.
        user_overlay = self._deep_merge(user_config, user_wendao)
        self._data = self._deep_merge(defaults, user_overlay)

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
