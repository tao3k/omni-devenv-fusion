"""
lazy_cache/config_cache.py
Configuration file caching with automatic format detection.

Supports TOML, JSON, YAML, and .conform.yaml formats.

Protocol-based design with slots=True.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .base import LazyCacheBase


class ConfigCache(LazyCacheBase[dict[str, Any]]):
    """Lazy cache for configuration files (TOML, YAML, JSON).

    Automatically detects file type and parses accordingly.

    Example:
        cache = ConfigCache(file_path=Path("/project/cog.toml"))
        config = cache.get()  # {"scopes": ["nix", "mcp", ...]}
    """

    __slots__ = ("_file_path",)

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize config cache.

        Args:
            file_path: Path to the config file.
            eager: If True, parse file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> dict[str, Any]:
        """Parse config file based on extension.

        Returns:
            Parsed configuration as dictionary.
        """
        if not self._file_path.exists():
            return {}

        content = self._file_path.read_text(encoding="utf-8")
        suffix = self._file_path.suffix.lower()

        # Handle TOML files
        if suffix == ".toml":
            try:
                import tomllib

                with open(self._file_path, "rb") as f:
                    return tomllib.load(f)
            except ImportError:
                import tomli

                with open(self._file_path, "rb") as f:
                    return tomli.load(f)

        # Handle JSON files
        if suffix == ".json":
            return json.loads(content)

        # Handle YAML files
        if suffix in (".yaml", ".yml"):
            try:
                import yaml

                return yaml.safe_load(content) or {}
            except ImportError:
                # Fallback: simple key-value parsing
                result: dict[str, str] = {}
                for line in content.split("\n"):
                    if ":" in line and not line.strip().startswith("#"):
                        key, value = line.split(":", 1)
                        result[key.strip()] = value.strip()
                return result

        # Handle .conform.yaml (special case for commit types)
        if suffix == ".conform.yaml":
            result: dict[str, Any] = {"types": []}
            found_types = re.findall(r"-\s+type:\s+([a-zA-Z0-9]+)", content)
            if found_types:
                result["types"] = list(set(found_types))
            return result

        return {}


__all__ = ["ConfigCache"]
