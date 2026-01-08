# config/commits.py
"""
Commit Configuration

Provides commit-related configuration functions.

Phase 33: Modularized from settings.py

Usage:
    from common.config.commits import get_commit_types, get_commit_scopes
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common.gitops import get_project_root


def get_commit_types() -> list[str]:
    """
    Get the list of valid commit types.

    Reads from cog.toml or .conform.yaml.
    Falls back to Conventional Commits defaults if config files not found.
    """
    from .settings import Settings

    settings = Settings()
    cog_path = get_project_root() / settings.get("config.cog_toml", "cog.toml")

    if cog_path.exists():
        try:
            import tomllib

            with open(cog_path, "rb") as f:
                cog_config = tomllib.load(f)
            if "commit" in cog_config and "types" in cog_config["commit"]:
                return cog_config["commit"]["types"]
        except Exception:
            pass

    # Try to read from .conform.yaml
    conform_path = get_project_root() / settings.get("config.conform_yaml", ".conform.yaml")
    if conform_path.exists():
        try:
            content = conform_path.read_text()
            import re

            types = re.findall(r"-\s*type:\s*([a-zA-Z0-9]+)", content)
            if types:
                return list(set(types))
        except Exception:
            pass

    # Fallback to Conventional Commits defaults
    return ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore"]


def get_commit_scopes() -> list[str]:
    """
    Get the list of valid commit scopes.

    Reads from cog.toml if available.
    Falls back to project-specific defaults if not configured.
    """
    from .settings import Settings

    settings = Settings()
    cog_path = get_project_root() / settings.get("config.cog_toml", "cog.toml")

    if cog_path.exists():
        try:
            import tomllib

            with open(cog_path, "rb") as f:
                cog_config = tomllib.load(f)
            if "commit" in cog_config and "scopes" in cog_config["commit"]:
                return cog_config["commit"]["scopes"]
        except Exception:
            pass

    # Fallback to project defaults
    return ["nix", "mcp", "router", "docs", "cli", "deps", "ci", "data"]


def get_commit_protocol() -> str:
    """Get the default commit protocol."""
    from .settings import get_setting

    return get_setting("commit.protocol", "stop_and_ask")


__all__ = [
    "get_commit_types",
    "get_commit_scopes",
    "get_commit_protocol",
]
