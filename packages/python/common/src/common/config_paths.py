# mcp-core/config_paths.py
"""
Unified Configuration Paths Manager

Centralizes all configuration file paths in one place:
- Reads paths from settings.yaml (conf_dir/references.yaml)
- Supports --conf flag to override configuration directory
- Resolves relative paths using git toplevel as base
- Supports YAML-based path configuration

Philosophy:
- Single source of truth for configuration paths
- Decouple path logic from business logic
- Support dynamic configuration updates

Usage:
    from common.mcp_core.config_paths import (
        get_api_key,
        get_mcp_config_path,
        get_anthropic_settings_path,
        get_project_config_path,
    )

    # Get API key from .claude/settings.json
    api_key = get_api_key()

    # Get MCP config path
    mcp_path = get_mcp_config_path()
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

# Project root detection using GitOps
from common.gitops import get_project_root

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


class ConfigPaths:
    """
    Unified Configuration Paths Manager.

    Reads path configurations from settings.yaml and resolves paths
    relative to project root (git toplevel).

    Example settings.yaml:
        api:
          anthropic_settings: ".claude/settings.json"
        mcp:
          config_file: ".mcp.json"
    """

    _instance: Optional["ConfigPaths"] = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls) -> "ConfigPaths":
        """Create singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data: dict[str, Any] = {}
        return cls._instance

    def __init__(self) -> None:
        """Initialize config paths manager."""
        pass

    def _ensure_loaded(self) -> None:
        """Ensure configuration is loaded, thread-safe with double-check locking."""
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._load()
                    self._loaded = True

    def _load(self) -> None:
        """Load configuration from settings.yaml."""
        project_root = get_project_root()
        conf_dir = get_conf_dir()
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

    def _resolve_path(self, path: str | None) -> Path | None:
        """Resolve path relative to project root if it's a relative path."""
        if path is None:
            return None

        project_root = get_project_root()
        path_str = str(path)
        path_obj = Path(path_str)

        # If path is relative, resolve from project root
        if not path_obj.is_absolute():
            return project_root / path_obj

        return path_obj

    def _get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        self._ensure_loaded()

        keys = key.split(".")
        value = self._data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    # =============================================================================
    # API Key Configuration
    # =============================================================================

    def get_anthropic_settings_path(self) -> Path | None:
        """Get the path to .claude/settings.json for API key."""
        path_str = self._get("api.anthropic_settings", ".claude/settings.json")
        return self._resolve_path(path_str)

    def get_api_base_url(self) -> str | None:
        """
        Get API base URL.

        Reads from settings.yaml -> api.base_url
        Falls back to .claude/settings.json -> env.ANTHROPIC_BASE_URL

        Returns:
            API base URL string or None (uses default Anthropic API)
        """
        # Try settings.yaml first
        base_url = self._get("api.base_url")
        if base_url:
            return base_url

        # Fall back to .claude/settings.json
        settings_path = self.get_anthropic_settings_path()
        if settings_path and settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    config = json.load(f)
                env = config.get("env", {})
                base_url = env.get("ANTHROPIC_BASE_URL")
                if base_url:
                    return base_url
            except Exception:
                pass

        return None

    def get_api_key(self, env_var: str = "ANTHROPIC_API_KEY") -> str | None:
        """
        Get Anthropic API key.

        Priority:
        1. Environment variable ANTHROPIC_API_KEY
        2. From .claude/settings.json (parsed via settings.yaml path)
        3. From .mcp.json (fallback)
        4. None

        Args:
            env_var: Environment variable name for API key

        Returns:
            API key string or None
        """
        # 1. Check environment variable first
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

        # 2. Try .claude/settings.json
        settings_path = self.get_anthropic_settings_path()
        if settings_path and settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    config = json.load(f)
                env = config.get("env", {})
                api_key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
                if api_key:
                    return api_key
            except Exception:
                pass

        # 3. Try .mcp.json as fallback
        mcp_path = self.get_mcp_config_path()
        if mcp_path and mcp_path.exists():
            try:
                with open(mcp_path, "r") as f:
                    config = json.load(f)
                servers = config.get("mcpServers", {})
                orchestrator = servers.get("orchestrator", {})
                env = orchestrator.get("env", {})
                api_key = env.get("ANTHROPIC_API_KEY")
                if api_key:
                    return api_key
            except Exception:
                pass

        return None

    # =============================================================================
    # MCP Configuration
    # =============================================================================

    def get_mcp_config_path(self) -> Path | None:
        """Get the path to .mcp.json."""
        path_str = self._get("mcp.config_file", ".mcp.json")
        return self._resolve_path(path_str)

    def get_mcp_config(self) -> dict[str, Any] | None:
        """Load and return the MCP configuration."""
        mcp_path = self.get_mcp_config_path()
        if mcp_path and mcp_path.exists():
            try:
                with open(mcp_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_mcp_server_config(self, server_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific MCP server."""
        config = self.get_mcp_config()
        if config:
            servers = config.get("mcpServers", {})
            return servers.get(server_name)
        return None

    def get_mcp_timeout(self, server_name: str | None = None) -> int:
        """Get MCP timeout in seconds."""
        timeout = self._get("mcp.timeout", 120)
        if server_name:
            server_config = self.get_mcp_server_config(server_name)
            if server_config and isinstance(server_config, dict):
                return server_config.get("timeout", timeout)
        return timeout

    # =============================================================================
    # Project Configuration
    # =============================================================================

    def get_cog_toml_path(self) -> Path | None:
        """Get the path to cog.toml."""
        path_str = self._get("config.cog_toml", "cog.toml")
        return self._resolve_path(path_str)

    def get_conform_yaml_path(self) -> Path | None:
        """Get the path to .conform.yaml."""
        path_str = self._get("config.conform_yaml", ".conform.yaml")
        return self._resolve_path(path_str)

    def get_project_root(self) -> Path:
        """Get the project root path."""
        return get_project_root()

    # =============================================================================
    # Utility Methods
    # =============================================================================

    def list_config_files(self) -> list[dict[str, str]]:
        """List all configuration files and their paths."""
        configs = [
            {
                "name": "settings.yaml",
                "path": str(Path(get_conf_dir()) / "settings.yaml"),
                "exists": (Path(get_conf_dir()) / "settings.yaml").exists(),
            },
            {
                "name": "anthropic_settings",
                "path": str(self.get_anthropic_settings_path()),
                "exists": self.get_anthropic_settings_path().exists()
                if self.get_anthropic_settings_path()
                else False,
            },
            {
                "name": "mcp_config",
                "path": str(self.get_mcp_config_path()),
                "exists": self.get_mcp_config_path().exists()
                if self.get_mcp_config_path()
                else False,
            },
            {
                "name": "cog_toml",
                "path": str(self.get_cog_toml_path()),
                "exists": self.get_cog_toml_path().exists() if self.get_cog_toml_path() else False,
            },
        ]
        return configs

    def reload(self) -> None:
        """Force reload configuration."""
        with self._instance_lock:
            self._loaded = False
            self._ensure_loaded()


# =============================================================================
# Convenience Functions
# =============================================================================


def get_config_paths() -> ConfigPaths:
    """Get the ConfigPaths singleton instance."""
    return ConfigPaths()


def get_api_key(env_var: str = "ANTHROPIC_API_KEY") -> str | None:
    """
    Get Anthropic API key.

    Reads from settings.yaml for path configuration.
    """
    return get_config_paths().get_api_key(env_var)


def get_mcp_config() -> dict[str, Any] | None:
    """Get MCP configuration from .mcp.json."""
    return get_config_paths().get_mcp_config()


def get_anthropic_settings_path() -> Path | None:
    """Get path to .claude/settings.json."""
    return get_config_paths().get_anthropic_settings_path()


def get_mcp_config_path() -> Path | None:
    """Get path to .mcp.json."""
    return get_config_paths().get_mcp_config_path()


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "ConfigPaths",
    "get_config_paths",
    "get_api_key",
    "get_mcp_config",
    "get_anthropic_settings_path",
    "get_mcp_config_path",
    "AuthorizationWait",
    "format_authorization_wait",
]


# =============================================================================
# Authorization Wait Manager - Forces User Confirmation
# =============================================================================


class AuthorizationWait:
    """
    Manages authorization wait state.

    This class ensures that after getting an auth_token:
    1. The system waits for user confirmation
    2. Only proceeds when user explicitly says "run just agent-commit"
    3. Rejects any attempt to bypass the confirmation

    Usage:
        wait = AuthorizationWait(auth_token="xxx", command="just agent-commit...")
        if wait.is_waiting():
            return wait.format_wait_message()
        # Then user says "run just agent-commit"
        if wait.confirm("run just agent-commit"):
            # Execute the command
            pass
    """

    _pending: dict[str, dict] = {}

    def __init__(self, auth_token: str, command: str, context: str = ""):
        self.auth_token = auth_token
        self.command = command
        self.context = context

    def is_waiting(self) -> bool:
        """Check if this authorization is still waiting."""
        return self.auth_token in AuthorizationWait._pending

    def save(self) -> None:
        """Save this authorization as pending."""
        AuthorizationWait._pending[self.auth_token] = {
            "command": self.command,
            "context": self.context,
            "created_at": __import__("time").time(),
        }

    def confirm(self, user_input: str) -> bool:
        """
        Check if user input confirms the authorization.

        Args:
            user_input: The user's input string

        Returns:
            True if user input matches the confirmation phrase
        """
        # Check for the specific confirmation phrase
        confirmation_phrases = [
            "run just agent-commit",
            "just agent-commit",
            "agent-commit",
        ]

        user_input_lower = user_input.lower()
        for phrase in confirmation_phrases:
            if phrase in user_input_lower:
                # Remove this authorization from pending
                AuthorizationWait._pending.pop(self.auth_token, None)
                return True

        return False

    def format_wait_message(self) -> str:
        """Format the waiting message."""
        return f"""
## 🔐 Authorization Required

**Auth Token:** `{self.auth_token}`

**Command to execute:**
```
{self.command}
```

### ⚠️ IMPORTANT: Do NOT proceed without user confirmation!

**To proceed, you MUST say exactly:**
> `run just agent-commit`

**I will wait for your confirmation before executing.**

---
*This is a Human-in-the-loop authorization checkpoint.*
"""

    @classmethod
    def check_confirmation(
        cls, user_input: str, auth_token: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if user input confirms any pending authorization.

        Args:
            user_input: The user's input
            auth_token: Optional specific token to check

        Returns:
            (confirmed, command) - True if confirmed, and the command if found
        """
        for token, data in cls._pending.items():
            if auth_token and token != auth_token:
                continue

            # Check if user input confirms
            user_input_lower = user_input.lower()
            if "run just agent-commit" in user_input_lower:
                # Remove from pending
                cls._pending.pop(token, None)
                return True, data.get("command")

        return False, None

    @classmethod
    def clear_all(cls) -> None:
        """Clear all pending authorizations."""
        cls._pending.clear()


def format_authorization_wait(auth_token: str, command: str) -> str:
    """
    Format an authorization wait message.

    Use this when you get an auth_token and need to wait for user confirmation.

    Args:
        auth_token: The authorization token
        command: The command to execute

    Returns:
        Formatted message asking for user confirmation
    """
    wait = AuthorizationWait(auth_token=auth_token, command=command)
    wait.save()
    return wait.format_wait_message()
