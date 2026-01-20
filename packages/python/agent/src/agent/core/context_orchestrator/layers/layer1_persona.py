"""
layer1_persona.py - Layer 1: System Persona (The "Soul").
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Tuple

import structlog

from common.gitops import get_project_root
from common.mcp_core.reference_library import get_reference_path

from .layer_base import ContextLayer

logger = structlog.get_logger(__name__)

# Tokenizer - imported from parent module
_ENCODER = None


def _get_encoder():
    """Lazy import tiktoken encoder."""
    global _ENCODER
    if _ENCODER is None:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    return len(encoder.encode(text))


class Layer1_SystemPersona(ContextLayer):
    """Layer 1: System Persona - The Soul of the agent."""

    name = "system_persona"
    priority = 1

    # Class-level cache for system context
    _cached_context: str | None = None
    _cached_at: float = 0
    _cached_mtime: float = 0
    _cache_ttl: float = 300.0  # 5 minutes

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        project_root = get_project_root()

        # 1. Load System Context XML (SSOT: references.yaml)
        sys_ctx_path = project_root / get_reference_path("context.system_context")
        base_prompt = ""

        if sys_ctx_path.exists():
            current_mtime = sys_ctx_path.stat().st_mtime

            if (
                self._cached_context is not None
                and self._cached_mtime == current_mtime
                and time.time() - self._cached_at < self._cache_ttl
            ):
                base_prompt = self._cached_context
                logger.debug("Using cached system_context.xml")
            else:
                content = sys_ctx_path.read_text(encoding="utf-8")
                self._cached_context = content
                self._cached_mtime = current_mtime
                self._cached_at = time.time()
                base_prompt = content
                logger.debug("Loaded and cached system_context.xml")
        else:
            # Fallback for bootstrapping
            base_prompt = """<system_context>
  <role>Omni-Dev: Advanced Cognitive Code Agent</role>
  <architecture>Trinity (CCA)</architecture>
</system_context>"""

        # 2. Load Scratchpad (Current Plan)
        scratchpad = ""
        scratchpad_path = project_root / "SCRATCHPAD.md"
        if scratchpad_path.exists():
            content = scratchpad_path.read_text(encoding="utf-8")
            scratchpad = f"\n<current_plan>\n{content}\n</current_plan>"

        final_content = f"{base_prompt}{scratchpad}"
        return final_content, _count_tokens(final_content)


__all__ = ["Layer1_SystemPersona"]
