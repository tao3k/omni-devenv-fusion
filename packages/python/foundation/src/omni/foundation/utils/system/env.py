"""
utils/env.py
Environment variable utilities.

Protocol-based design.

Provides environment variable loading and access utilities.
"""

from __future__ import annotations

import json
import os


def load_env_from_file(
    config_key: str | None = None,
    env_key: str | None = None,
    config_file: str | None = None,
) -> dict[str, str]:
    """Load environment variables from a JSON config file.

    Supports both flat structure and nested mcpServers structure.

    Args:
        config_key: Config key to extract (e.g., "orchestrator", "coder")
        env_key: Environment variable name for config file path
        config_file: Explicit config file path

    Returns:
        Dict of environment variables
    """
    if config_file is None:
        config_file = env_key or os.environ.get("MCP_CONFIG_FILE", ".mcp.json")

    if not os.path.exists(config_file):
        return {}

    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # Handle flat config or nested mcpServers config
    if config_key and isinstance(data.get("mcpServers"), dict):
        server_config = data["mcpServers"].get(config_key, {})
        env_vars = server_config.get("env", {}) if isinstance(server_config, dict) else {}
        flat_env = data if isinstance(data, dict) else {}
    else:
        env_vars = data if isinstance(data, dict) else {}
        flat_env = data if isinstance(data, dict) else {}

    # Merge flat env with server-specific env (server config takes precedence)
    merged: dict[str, str] = {}
    for source in (flat_env, env_vars):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, str):
                    merged[key] = value

    return merged


def get_env(key: str, env_vars: dict[str, str] | None = None, default: str | None = None) -> str:
    """Get environment variable with fallback chain.

    Args:
        key: Environment variable key
        env_vars: Pre-loaded env vars dict
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    if env_vars is None:
        env_vars = {}

    return env_vars.get(key) or os.environ.get(key) or default  # type: ignore[return-value]


__all__ = ["load_env_from_file", "get_env"]
