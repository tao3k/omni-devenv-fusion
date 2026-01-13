# inference - LLM Inference Module

"""
LLM Inference Module

Phase 30: Modularized for testability.
Phase 37: Configuration-driven from settings.yaml.

Modules:
- client.py: InferenceClient class
- personas.py: Persona definitions
- api.py: API key loading and config

Usage:
    from mcp_core.inference import InferenceClient, PERSONAS, build_persona_prompt

    client = InferenceClient()
    result = await client.complete("You are a Python expert.", "Write a function to sort a list.")
"""

from .client import InferenceClient
from .personas import PERSONAS, load_personas_from_file, get_persona, build_persona_prompt
from .api import load_api_key, get_inference_config


# Backward compatibility - expose _load_api_key_from_config
def _load_api_key_from_config() -> str:
    """Load API key from config (backward compatibility)."""
    return load_api_key() or ""


# Backward compatibility - expose DEFAULT_* values from settings
# These are evaluated at import time, but read from config
_config = get_inference_config()
DEFAULT_MODEL = _config["model"]
DEFAULT_BASE_URL = _config["base_url"]
DEFAULT_TIMEOUT = _config["timeout"]
DEFAULT_MAX_TOKENS = _config["max_tokens"]


__all__ = [
    # Client
    "InferenceClient",
    "get_inference_config",
    # Defaults (backward compat)
    "DEFAULT_MODEL",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_TOKENS",
    # Personas
    "PERSONAS",
    "load_personas_from_file",
    "get_persona",
    "build_persona_prompt",
    # API
    "load_api_key",
    "_load_api_key_from_config",
]
