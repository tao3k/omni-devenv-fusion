# inference/api.py
"""
API Key loading for inference module.

Modularized from inference.py.
Configuration-driven API key loading from settings.yaml.
Supports reading from .claude/settings.json via get_anthropic_api_key().
"""

from omni.foundation.api.api_key import get_anthropic_api_key
from omni.foundation.config.settings import get_setting


def get_inference_config() -> dict:
    """Get inference configuration from settings.yaml.

    Returns:
        dict with keys: api_key_env, base_url, model, timeout, max_tokens
    """
    return {
        "api_key_env": get_setting("inference.api_key_env", "ANTHROPIC_API_KEY"),
        "base_url": get_setting("inference.base_url", "https://api.anthropic.com"),
        "model": get_setting("inference.model", "claude-sonnet-4-20250514"),
        "timeout": get_setting("inference.timeout", 120),
        "max_tokens": get_setting("inference.max_tokens", 4096),
    }


def load_api_key() -> str | None:
    """Load API key from best available source.

    Priority:
    1. Configured env var (from settings.yaml inference.api_key_env)
    2. .claude/settings.json (via get_anthropic_api_key)
    3. Environment variables (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN)

    Returns:
        API key string or None
    """
    config = get_inference_config()
    api_key_env = config["api_key_env"]

    # Try configured env var first
    import os

    api_key = os.environ.get(api_key_env)
    if api_key:
        return api_key.strip('"').strip("'")

    # Try .claude/settings.json and other sources via get_anthropic_api_key
    api_key = get_anthropic_api_key()
    if api_key:
        return api_key

    # Fallback to ANTHROPIC_API_KEY if different
    if api_key_env != "ANTHROPIC_API_KEY":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return api_key.strip('"').strip("'")

    return None


__all__ = ["get_inference_config", "load_api_key"]
