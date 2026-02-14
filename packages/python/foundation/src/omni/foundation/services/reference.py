# mcp-core/reference_library.py
"""
Reference Knowledge Library - Knowledge Document Path Resolution

System default: <project_root>/packages/conf/references.yaml
User override:  $PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml (e.g. .config/... or --conf <dir>)

User config is merged on top of system default (deep merge).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from omni.foundation.config.directory import get_conf_dir as _get_conf_dir
from omni.foundation.config.directory import set_conf_dir as _set_conf_dir
from omni.foundation.config.dirs import PRJ_CONFIG

# Project root detection using GitOps
from omni.foundation.runtime.gitops import get_project_root


def get_references_config_path() -> Path:
    """
    Path to the references config file itself (references.yaml).

    Precedence:
      1. OMNI_REFERENCES_YAML env (if set)
      2. User override: $PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml
      3. System default: <project_root>/packages/conf/references.yaml

    Returns:
        Path to the active references config file (may not exist for 3 if repo has none).
    """
    env_path = os.environ.get("OMNI_REFERENCES_YAML")
    if env_path:
        return Path(env_path)

    user_refs = PRJ_CONFIG("omni-dev-fusion", "references.yaml")
    if user_refs.exists():
        return user_refs

    try:
        return get_project_root() / "packages" / "conf" / "references.yaml"
    except Exception:
        return Path("packages/conf/references.yaml")


# YAML support (try PyYAML first, fallback to simple parsing)
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def set_conf_dir(path: str) -> None:
    """Set config directory via canonical PRJ_CONFIG_HOME API."""
    _set_conf_dir(path)
    # Config root changed; invalidate singleton cache so next read reloads.
    ReferenceLibrary._instance = None


def get_conf_dir() -> str:
    """Get config directory via canonical PRJ_CONFIG_HOME API."""
    return _get_conf_dir()


class ReferenceLibrary:
    """
    Reference Knowledge Library - Singleton for knowledge document references.

    Load order: 1) system default packages/conf/references.yaml, 2) user override
    $PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml (user layer wins).

    Usage:
        ref = ReferenceLibrary()
        doc_path = ref.get_path("specs.dir")  # Returns: "assets/specs"
    """

    _instance: ReferenceLibrary | None = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls) -> ReferenceLibrary:
        """Create singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data: dict[str, Any] = {}
        return cls._instance

    def __init__(self) -> None:
        """Initialize reference library."""
        pass

    def _ensure_loaded(self) -> None:
        """Ensure references are loaded, thread-safe with double-check locking."""
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._load()
                    self._loaded = True

    def _load(self) -> None:
        """Load references: system default from packages/conf, then user override from config dir."""
        root = get_project_root()
        # System-level default (lives with code under packages/conf)
        system_refs = root / "packages" / "conf" / "references.yaml"
        # User override (--conf or $PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml)
        user_refs = PRJ_CONFIG("omni-dev-fusion", "references.yaml")

        self._data = {}
        # 1. Load system default
        if system_refs.exists():
            try:
                content = system_refs.read_text(encoding="utf-8")
                if YAML_AVAILABLE:
                    import yaml

                    self._data = yaml.safe_load(content) or {}
                else:
                    self._data = self._parse_simple_yaml(content)
            except Exception:
                pass
        # 2. User override (merge on top)
        if user_refs.exists():
            try:
                content = user_refs.read_text(encoding="utf-8")
                if YAML_AVAILABLE:
                    import yaml

                    overrides = yaml.safe_load(content) or {}
                    self._deep_merge(overrides, self._data)
                else:
                    overrides = self._parse_simple_yaml(content)
                    self._deep_merge(overrides, self._data)
            except Exception:
                pass

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

    @staticmethod
    def _deep_merge(source: dict[str, Any], target: dict[str, Any]) -> None:
        """Merge source into target in place; source values override."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                ReferenceLibrary._deep_merge(value, target[key])
            else:
                target[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a reference value using dot notation.

        Args:
            key: Dot-separated path (e.g., "specs.dir")
            default: Default value if key not found

        Returns:
            The reference value or default
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
        Get a document path reference.

        Args:
            key: Dot-separated path (e.g., "specs.dir")

        Returns:
            Document path string, or empty string if not found
        """
        result = self.get(key)
        return result if result else ""

    def get_cache(self, key: str) -> str:
        """
        Get a cache class name reference.

        Args:
            key: Dot-separated path (e.g., "writing_style.cache")

        Returns:
            Cache class name, or empty string if not found
        """
        return self.get(key, "")

    def has_reference(self, key: str) -> bool:
        """
        Check if a reference exists.

        Args:
            key: Dot-separated path to check

        Returns:
            True if reference exists, False otherwise
        """
        return self.get(key) is not None

    def get_config(self) -> dict[str, Any]:
        """Return full merged config (system default + user override) as a copy."""
        import copy

        self._ensure_loaded()
        return copy.deepcopy(self._data)

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get an entire reference section.

        Args:
            section: Section name (e.g., "specs")

        Returns:
            Section dictionary or empty dict
        """
        self._ensure_loaded()
        return self._data.get(section, {})

    def list_sections(self) -> list[str]:
        """
        List all reference sections.

        Returns:
            List of section names
        """
        self._ensure_loaded()
        return list(self._data.keys())

    def reload(self) -> None:
        """Force reload references from YAML file."""
        with self._instance_lock:
            self._loaded = False
            self._ensure_loaded()

    @property
    def is_loaded(self) -> bool:
        """Check if references have been loaded."""
        return self._loaded


# =============================================================================
# Convenience Functions
# =============================================================================


class _Ref:
    """Global reference accessor - use ref() or REF for single-source path resolution.

    Usage:
        from omni.foundation.services.reference import ref, REF

        # Get path as Path object (supports / operator for chaining)
        harvest_dir = ref("harvested_knowledge.dir")
        commands_path = ref("skills.directory") / "git" / "scripts" / "commands.py"

        # Check existence
        if ref("specs.dir").exists():
            ...
    """

    def __call__(self, key: str) -> Path:
        """Get a path reference as Path object (from references.yaml).

        Args:
            key: Dot-separated path (e.g., "harvested_knowledge.dir")

        Returns:
            Path object resolved from project root, or Path() if key not in config
        """
        lib = ReferenceLibrary()
        value = lib.get_path(key)

        if not value:
            return Path()

        # Return absolute path
        if Path(value).is_absolute():
            return Path(value)

        # Resolve relative to project root
        root = get_project_root()
        return root / value

    def exists(self, key: str) -> bool:
        """Check if a reference path exists."""
        return self(key).exists()

    def __truediv__(self, key: str) -> Path:
        """Support ref("key") / "subpath" chaining."""
        return self(key)


# Global instance for convenience
ref = _Ref()
REF = ref  # Alias for cleaner imports


def get_reference_cache(key: str) -> str:
    """
    Get a cache class name reference.

    Args:
        key: Dot-separated path (e.g., "writing_style.cache")

    Returns:
        Cache class name
    """
    ref = ReferenceLibrary()
    return ref.get_cache(key)


def has_reference(key: str) -> bool:
    """
    Check if a reference exists.

    Args:
        key: Dot-separated path to check

    Returns:
        True if reference exists
    """
    ref = ReferenceLibrary()
    return ref.has_reference(key)


def list_reference_sections() -> list[str]:
    """List all reference sections."""
    ref = ReferenceLibrary()
    return ref.list_sections()


# =============================================================================
# Export (public API: config path only; ReferenceLibrary / ref remain for internal use)
# =============================================================================

__all__ = [
    "get_references_config_path",
]
