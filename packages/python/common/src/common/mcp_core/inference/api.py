# inference/api.py
"""
API Key loading for inference module.

Phase 30: Modularized from inference.py.
"""

import os
from typing import Optional


def load_api_key() -> Optional[str]:
    """Load API key from project config files.

    Checks in order:
    1. Environment variable ANTHROPIC_API_KEY
    2. .claude/settings.json (via agent/settings.yaml path)
    3. .mcp.json (Claude Desktop format)

    Returns:
        API key string or None
    """
    # Priority 1: Environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return api_key

    # Priority 2: Delegate to common api_key module
    try:
        from common.mcp_core.api_key import get_anthropic_api_key

        return get_anthropic_api_key()
    except ImportError:
        pass

    return None


__all__ = ["load_api_key"]
