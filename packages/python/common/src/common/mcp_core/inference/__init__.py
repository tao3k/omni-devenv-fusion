# inference - LLM Inference Module

"""
LLM Inference Module

Phase 30: Modularized for testability.

Modules:
- client.py: InferenceClient class
- personas.py: Persona definitions
- api.py: API key loading

Usage:
    from mcp_core.inference import InferenceClient, PERSONAS, build_persona_prompt

    client = InferenceClient()
    result = await client.complete("You are a Python expert.", "Write a function to sort a list.")
"""

from .client import (
    InferenceClient,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_TOKENS,
)
from .personas import PERSONAS, load_personas_from_file, get_persona, build_persona_prompt
from .api import load_api_key


# Backward compatibility - expose _load_api_key_from_config
def _load_api_key_from_config() -> str:
    """Load API key from config (backward compatibility)."""
    return load_api_key() or ""


__all__ = [
    # Client
    "InferenceClient",
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
