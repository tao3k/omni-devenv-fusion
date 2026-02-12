# api_key.py
"""
Unified API Key Management Module

Modularized.

Provides consistent API key loading from multiple sources:
1. Environment variable (ANTHROPIC_API_KEY)
2. .claude/settings.json (via settings.yaml path)
3. .mcp.json (Claude Desktop format)

Usage:
    from omni.foundation.api.api_key import get_anthropic_api_key

    api_key = get_anthropic_api_key()  # Auto-loads from best available source
"""

import json
import os
from pathlib import Path

import structlog

logger = structlog.get_logger("mcp-core.api-key")


def _find_project_root() -> Path:
    """Find project root (git toplevel)."""
    from omni.foundation.runtime.gitops import get_project_root

    return get_project_root()


def _load_settings_yaml() -> dict:
    """Load API config from the merged settings view."""
    from omni.foundation.config.settings import get_settings

    return get_settings().get("api", {})


def _get_settings_json_path() -> Path | None:
    """Get .claude/settings.json path from settings.yaml."""
    api_settings = _load_settings_yaml()
    anthropic_path = api_settings.get("anthropic_settings", ".claude/settings.json")
    project_root = _find_project_root()
    return project_root / anthropic_path


def get_anthropic_api_key() -> str | None:
    """
    Get Anthropic API key from the best available source.

    Priority:
    1. Environment variable ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN
    2. .claude/settings.json (reads from settings.yaml path)
    3. .mcp.json (Claude Desktop format)

    Supports both standard Anthropic format (ANTHROPIC_API_KEY) and
    MiniMax compatible format (ANTHROPIC_AUTH_TOKEN).

    Returns:
        API key string or None if not found
    """
    # 1. Check environment variables first
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if api_key:
        logger.debug("API key loaded from environment variable")
        return api_key

    project_root = _find_project_root()

    # 2. Try .claude/settings.json (via settings.yaml path)
    settings_path = _get_settings_json_path()
    if settings_path and settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                data = json.load(f)

            # Try top-level key
            api_key = data.get("ANTHROPIC_API_KEY") or data.get("ANTHROPIC_AUTH_TOKEN")
            if api_key:
                logger.debug("API key loaded from .claude/settings.json (top-level)")
                return api_key

            # Try nested env format (supports MiniMax compatible format)
            if env := data.get("env", {}):
                api_key = env.get("ANTHROPIC_API_KEY") or env.get("ANTHROPIC_AUTH_TOKEN")
                if api_key:
                    logger.debug("API key loaded from .claude/settings.json (env)")
                    return api_key

        except Exception as e:
            logger.warning("Failed to load .claude/settings.json", error=str(e))

    # 3. Try .mcp.json (Claude Desktop format)
    mcp_path = project_root / ".mcp.json"
    if mcp_path.exists():
        try:
            with open(mcp_path, encoding="utf-8") as f:
                data = json.load(f)

            # Try mcpServers.orchestrator.env.ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN
            if servers := data.get("mcpServers", {}):
                if orchestrator := servers.get("orchestrator", {}):
                    if env := orchestrator.get("env", {}):
                        api_key = env.get("ANTHROPIC_API_KEY") or env.get("ANTHROPIC_AUTH_TOKEN")
                        if api_key:
                            logger.debug("API key loaded from .mcp.json")
                            return api_key

        except Exception as e:
            logger.warning("Failed to load .mcp.json", error=str(e))

    logger.warning("No API key found in any source")
    return None


def ensure_api_key() -> str:
    """
    Get API key, raising RuntimeError if not available.

    Returns:
        API key string

    Raises:
        RuntimeError: If no API key can be loaded
    """
    api_key = get_anthropic_api_key()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found. Please set it via:\n"
            "1. Environment variable: export ANTHROPIC_API_KEY=sk-...\n"
            "2. .claude/settings.json (path configured in agent/settings.yaml)\n"
            "3. .mcp.json: mcpServers.orchestrator.env.ANTHROPIC_API_KEY"
        )
    return api_key


__all__ = [
    "ensure_api_key",
    "get_anthropic_api_key",
]
