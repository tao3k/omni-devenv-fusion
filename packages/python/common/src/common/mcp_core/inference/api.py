# inference/api.py
"""
API Key loading for inference module.

Phase 30: Modularized from inference.py.
Phase 37: Configuration-driven API key loading from settings.yaml.
"""

import os
from typing import Optional

from common.settings import get_setting


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


def load_api_key() -> Optional[str]:
    """Load API key from configured environment variable.

    Reads the environment variable name from settings.yaml (inference.api_key_env).
    Falls back to ANTHROPIC_API_KEY if not configured.

    Returns:
        API key string or None
    """
    config = get_inference_config()
    api_key_env = config["api_key_env"]

    # Try configured env var first
    api_key = os.environ.get(api_key_env)
    if api_key:
        # Strip surrounding quotes if present (common config error)
        return api_key.strip('"').strip("'")

    # Fallback to ANTHROPIC_API_KEY if different
    if api_key_env != "ANTHROPIC_API_KEY":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return api_key.strip('"').strip("'")

    return None


__all__ = ["load_api_key", "get_inference_config"]
