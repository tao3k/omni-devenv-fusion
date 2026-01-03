# mcp-core/reference_library.py
"""
Reference Knowledge Library - Knowledge Document Path Resolution

Provides unified API for resolving knowledge document paths from references.yaml.
Uses YAML-based references for single source of truth.

Features:
- Reads from conf_dir/references.yaml (supports --conf flag)
- Dot-notation path access (e.g., "specs.dir")
- Thread-safe singleton pattern
- Hot reload support

Usage:
    from common.mcp_core.reference_library import ReferenceLibrary, get_reference_path

    # Default (uses agent/ directory)
    specs_dir = get_reference_path("specs.dir")  # Returns: "agent/specs"

    # Custom configuration directory
    python script.py --conf /path/to/conf
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Optional

# Project root detection using GitOps
from common.mcp_core.gitops import get_project_root

# YAML support (try PyYAML first, fallback to simple parsing)
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Global configuration directory (set by --conf flag)
_CONF_DIR: str | None = None
_conf_dir_lock = threading.Lock()


def set_conf_dir(path: str) -> None:
    """Set the configuration directory."""
    global _CONF_DIR
    with _conf_dir_lock:
        _CONF_DIR = path


def get_conf_dir() -> str:
    """Get the configuration directory."""
    global _CONF_DIR
    if _CONF_DIR is not None:
        return _CONF_DIR

    # Parse --conf from command line args
    args = sys.argv
    for i, arg in enumerate(args):
        if arg == "--conf" and i + 1 < len(args):
            _CONF_DIR = args[i + 1]
            return _CONF_DIR
        if arg.startswith("--conf="):
            _CONF_DIR = arg.split("=", 1)[1]
            return _CONF_DIR

    # Default to agent/
    _CONF_DIR = "agent"
    return _CONF_DIR


class ReferenceLibrary:
    """
    Reference Knowledge Library - Singleton for knowledge document references.

    Reads from conf_dir/references.yaml and provides path resolution.

    Usage:
        ref = ReferenceLibrary()
        doc_path = ref.get_path("specs.dir")  # Returns: "agent/specs"
    """

    _instance: Optional["ReferenceLibrary"] = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls) -> "ReferenceLibrary":
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
        """Load references from conf_dir/references.yaml."""
        project_root = get_project_root()
        conf_dir = get_conf_dir()
        refs_path = project_root / conf_dir / "references.yaml"

        if not refs_path.exists():
            self._data = {}
            return

        try:
            content = refs_path.read_text(encoding="utf-8")
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

def get_reference_path(key: str) -> str:
    """
    Get a document path reference.

    Args:
        key: Dot-separated path (e.g., "specs.dir")

    Returns:
        Document path string
    """
    ref = ReferenceLibrary()
    return ref.get_path(key)


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
# Export
# =============================================================================

__all__ = [
    "ReferenceLibrary",
    "get_reference_path",
    "get_reference_cache",
    "has_reference",
    "list_reference_sections",
]
