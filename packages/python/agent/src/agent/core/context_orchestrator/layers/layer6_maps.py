"""
layer6_maps.py - Layer 6: Code Maps (The "Map").
"""

from __future__ import annotations

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


class Layer6_CodeMaps(ContextLayer):
    """Layer 6: Code Maps - The Map of the codebase."""

    name = "code_maps"
    priority = 6

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 200:
            return "", 0

        try:
            omni = None
            try:
                import omni_core_rs

                omni = omni_core_rs
            except ImportError:
                pass

            if omni is None:
                return "", 0

            project_root = get_project_root()
            content_parts = ["\n<code_maps>"]

            # Get outline of key files
            key_files = [
                project_root / "packages/python/agent/src/agent/main.py",
                project_root / "packages/python/agent/src/agent/core/orchestrator/core.py",
            ]

            for file_path in key_files:
                if file_path.exists():
                    try:
                        outline = omni.get_file_outline(str(file_path))
                        if outline and "Error" not in outline:
                            rel_path = file_path.relative_to(project_root)
                            content_parts.append(f"\n### {rel_path}\n{outline}")
                    except Exception:
                        pass

            content_parts.append("\n</code_maps>")
            content = "".join(content_parts)
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Code maps failed: {e}")
            return "", 0


__all__ = ["Layer6_CodeMaps"]
