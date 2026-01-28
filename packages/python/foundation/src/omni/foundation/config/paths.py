"""
Unified Configuration Paths Manager (Refactored)

Layer 1: Semantic Configuration
Delegates physical path resolution to Layer 0 (dirs.py) via PRJ_SPEC standards.

Design Philosophy:
- Layered Architecture:
    - Layer 0: Environment & Base Dirs (dirs.py) -> Physical Locations
    - Layer 1: Configuration Logic (paths.py) -> Semantic Locations
- No more hardcoded strings for directories.
- Singleton pattern with lazy initialization.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Layer 0: Physical Directory Management
from .dirs import PRJ_CACHE, PRJ_CONFIG, PRJ_DATA, PRJ_DIRS, PRJ_RUNTIME

# =============================================================================
# Semantic Path Manager
# =============================================================================


class ConfigPaths:
    """
    语义化路径管理器 (Semantic Path Manager).

    Answers "WHERE is X?" - delegates physical location to dirs.py (Layer 0).

    Features:
    - Uses PRJ_DIRS/PRJ_CONFIG for environment-aware paths
    - Supports legacy paths for backward compatibility
    - Singleton pattern (stateless, all state in environment)

    Usage:
        from omni.foundation.config.paths import get_config_paths

        paths = get_config_paths()
        paths.project_root  # -> Path to git toplevel
        paths.get_log_dir() # -> Path to logs directory
    """

    _instance: ConfigPaths | None = None

    def __new__(cls) -> ConfigPaths:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # =============================================================================
    # Semantic Roots
    # =============================================================================

    @property
    def project_root(self) -> Path:
        """Git Toplevel (Immutable anchor).

        The project root is the parent of PRJ_CONFIG_HOME (e.g., .config/).
        This is typically the git toplevel directory.
        """
        return PRJ_DIRS.config_home.parent

    @property
    def settings_file(self) -> Path:
        """Main settings file: $PRJ_CONFIG_HOME/settings.yaml"""
        return PRJ_CONFIG("settings.yaml")

    # =============================================================================
    # Vendor Specific (Anthropic / OpenAI / etc)
    # =============================================================================

    def get_anthropic_settings_path(self) -> Path:
        """
        Get Anthropic settings path.

        Strategy:
        1. Modern: $PRJ_CONFIG_HOME/anthropic/settings.json
        2. Fallback: $PRJ_ROOT/.claude/settings.json
        """
        # 1. Try Modern Standard
        modern_path = PRJ_CONFIG("anthropic", "settings.json")
        if modern_path.exists():
            return modern_path

        # 2. Fallback
        return self.project_root / ".claude" / "settings.json"

    def get_api_key(self, env_var: str = "ANTHROPIC_API_KEY") -> str | None:
        """
        Get API key.

        Priority:
        1. Environment variable (ANTHROPIC_API_KEY)
        2. From anthropic/settings.json
        3. From mcp.json (orchestrator server)
        4. None
        """
        # 1. Check environment variable first
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

        # 2. Try anthropic/settings.json
        anthropic_path = self.get_anthropic_settings_path()
        if anthropic_path and anthropic_path.exists():
            try:
                with open(anthropic_path) as f:
                    config = json.load(f)
                env = config.get("env", {})
                api_key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
                if api_key:
                    return api_key
            except Exception:
                pass

        # 3. Try mcp.json as fallback
        mcp_path = self.get_mcp_config_path()
        if mcp_path and mcp_path.exists():
            try:
                with open(mcp_path) as f:
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

    def get_api_base_url(self) -> str | None:
        """
        Get API base URL.

        Priority:
        1. Environment variable ANTHROPIC_BASE_URL
        2. From settings.yaml -> api.base_url
        3. None (uses default Anthropic API)
        """
        # 1. Check environment variable first
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url:
            return base_url

        # 2. Try settings.yaml
        settings_path = self.settings_file
        if settings_path.exists():
            try:
                content = settings_path.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("api:") or line.startswith("api "):
                        continue
                    if "base_url:" in line:
                        url = line.split("base_url:")[1].strip()
                        url = url.strip('"').strip("'")
                        if url:
                            return url
            except Exception:
                pass

        return None

    # =============================================================================
    # Infrastructure (MCP / Logs / Data)
    # =============================================================================

    def get_mcp_config_path(self) -> Path:
        """
        MCP Server Configuration.
        Location: $PRJ_CONFIG_HOME/mcp.json
        """
        return PRJ_CONFIG("mcp.json")

    def get_mcp_config(self) -> dict[str, Any] | None:
        """Load and return the MCP configuration."""
        mcp_path = self.get_mcp_config_path()
        if mcp_path and mcp_path.exists():
            try:
                with open(mcp_path) as f:
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
        default_timeout = 120
        if server_name:
            server_config = self.get_mcp_server_config(server_name)
            if server_config and isinstance(server_config, dict):
                return server_config.get("timeout", default_timeout)
        return default_timeout

    def get_log_dir(self) -> Path:
        """
        Runtime Logs.
        Location: $PRJ_RUNTIME_DIR/logs (e.g., .run/logs)
        """
        return PRJ_RUNTIME.ensure_dir("logs")

    def get_data_dir(self, subdir: str = "") -> Path:
        """
        Persistent Data Storage.
        Location: $PRJ_DATA_HOME/<subdir>
        """
        if subdir:
            return PRJ_DATA.ensure_dir(subdir)
        return PRJ_DATA("")

    def get_cache_dir(self, subdir: str = "") -> Path:
        """Get cache directory ($PRJ_CACHE_HOME/subdir)."""
        if subdir:
            return PRJ_CACHE(subdir)
        return PRJ_CACHE("")

    # =============================================================================
    # Utility Methods
    # =============================================================================

    def list_config_files(self) -> list[dict[str, str | bool]]:
        """List all configuration files and their paths."""
        return [
            {
                "name": "settings.yaml",
                "path": str(self.settings_file),
                "exists": self.settings_file.exists(),
            },
            {
                "name": "anthropic_settings",
                "path": str(self.get_anthropic_settings_path()),
                "exists": self.get_anthropic_settings_path().exists(),
            },
            {
                "name": "mcp_config",
                "path": str(self.get_mcp_config_path()),
                "exists": self.get_mcp_config_path().exists(),
            },
        ]


# =============================================================================
# Singleton Accessor
# =============================================================================

_paths_instance: ConfigPaths | None = None


def get_config_paths() -> ConfigPaths:
    """Get the semantic paths manager (singleton)."""
    global _paths_instance
    if _paths_instance is None:
        _paths_instance = ConfigPaths()
    return _paths_instance


# =============================================================================
# Convenience Functions (Backward Compatibility)
# =============================================================================


def get_api_key(env_var: str = "ANTHROPIC_API_KEY") -> str | None:
    """Get Anthropic API key."""
    return get_config_paths().get_api_key(env_var)


def get_mcp_config() -> dict[str, Any] | None:
    """Get MCP configuration from mcp.json."""
    return get_config_paths().get_mcp_config()


def get_anthropic_settings_path() -> Path:
    """Get path to anthropic/settings.json."""
    return get_config_paths().get_anthropic_settings_path()


def get_mcp_config_path() -> Path:
    """Get path to mcp.json."""
    return get_config_paths().get_mcp_config_path()


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "AuthorizationWait",
    "ConfigPaths",
    "format_authorization_wait",
    "get_anthropic_settings_path",
    "get_api_key",
    "get_config_paths",
    "get_mcp_config",
    "get_mcp_config_path",
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
        """Check if user input confirms the authorization."""
        confirmation_phrases = [
            "run just agent-commit",
            "just agent-commit",
            "agent-commit",
        ]

        user_input_lower = user_input.lower()
        for phrase in confirmation_phrases:
            if phrase in user_input_lower:
                AuthorizationWait._pending.pop(self.auth_token, None)
                return True

        return False

    def format_wait_message(self) -> str:
        """Format the waiting message."""
        return f"""
## Authorization Required

**Auth Token:** `{self.auth_token}`

**Command to execute:**
```
{self.command}
```

### IMPORTANT: Do NOT proceed without user confirmation!

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
        """Check if user input confirms any pending authorization."""
        for token, data in cls._pending.items():
            if auth_token and token != auth_token:
                continue

            user_input_lower = user_input.lower()
            if "run just agent-commit" in user_input_lower:
                cls._pending.pop(token, None)
                return True, data.get("command")

        return False, None

    @classmethod
    def clear_all(cls) -> None:
        """Clear all pending authorizations."""
        cls._pending.clear()


def format_authorization_wait(auth_token: str, command: str) -> str:
    """Format an authorization wait message."""
    wait = AuthorizationWait(auth_token=auth_token, command=command)
    wait.save()
    return wait.format_wait_message()
