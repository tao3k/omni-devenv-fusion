# inference - LLM Inference Module

"""
LLM Inference Module

Modularized for testability.
Configuration-driven from settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml).

Modules:
- client.py: InferenceClient class
- personas.py: Persona definitions
- api.py: API key loading and config
- provider.py: Unified LLM Provider API (NEW - use this for all components)

Usage (NEW - Recommended):
    from omni.foundation.services.llm import get_llm_provider

    provider = get_llm_provider()
    result = await provider.complete("You are an expert.", "Extract entities from this text.")
    embeddings = provider.embed(["text1", "text2"])

"""

from .api import get_inference_config, load_api_key
from .client import InferenceClient
from .personas import PERSONAS, build_persona_prompt, get_persona, load_personas_from_file
from .provider import (
    LLMConfig,
    LLMResponse,
    LLMProvider,
    LiteLLMProvider,
    NoOpProvider,
    get_llm_provider,
    reset_provider,
    complete,
)

__all__ = [
    # Client
    "InferenceClient",
    "get_inference_config",
    # Personas
    "PERSONAS",
    "load_personas_from_file",
    "get_persona",
    "build_persona_prompt",
    # API
    "load_api_key",
    # Provider API (LiteLLM-based)
    "LLMConfig",
    "LLMResponse",
    "LLMProvider",
    "LiteLLMProvider",
    "NoOpProvider",
    "get_llm_provider",
    "reset_provider",
    # Convenience functions
    "complete",
]
