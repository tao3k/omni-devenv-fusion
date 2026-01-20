"""
layer5_env.py - Layer 5: Environment (The "Eyes").
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Tuple

import structlog

from common.gitops import get_project_root

from .layer_base import ContextLayer

logger = structlog.get_logger(__name__)

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


class Layer5_Environment(ContextLayer):
    """Layer 5: Environment State - The Eyes of the agent."""

    name = "environment"
    priority = 5

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        try:
            # Try to use omni_core_rs for Rust-accelerated sniffer
            omni = None
            try:
                import omni_core_rs

                omni = omni_core_rs
            except ImportError:
                pass

            if omni is None:
                return "", 0

            # Run sync sniffer in thread to not block event loop
            def _scan():
                return omni.get_environment_snapshot(str(get_project_root()))

            snapshot = await asyncio.to_thread(_scan)
            content = f"\n<environment_state>\n{snapshot}\n</environment_state>"
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Sniffer failed: {e}")
            return "", 0


__all__ = ["Layer5_Environment"]
