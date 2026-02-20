"""
Skill execution embedding override: MCP-first when running outside the MCP server.

When skills run from CLI (omni run ...), the runner invokes skill hooks before/after
each command. We set an embedding override so get_embedding_service().embed_batch()
delegates to the MCP server (if available), giving a warm path without starting
Ollama in the CLI process. When running inside the MCP server, no override is set.
"""

from __future__ import annotations

import os
from typing import Any

from omni.foundation.services.embedding import set_embedding_override
from omni.foundation.utils.asyncio import run_async_blocking


def _mcp_first_wrapper() -> Any:
    """Build a sync embedding wrapper that uses MCP when available (lazy, cached port)."""
    from omni.agent.cli.mcp_embed import detect_mcp_port, make_mcp_embed_func

    port: int | None = None

    def _ensure_port() -> int:
        nonlocal port
        if port is None:
            port = run_async_blocking(detect_mcp_port())
        return port or 0

    class _Wrapper:
        def embed(self, text: str) -> list[list[float]]:
            p = _ensure_port()
            if p <= 0:
                from omni.foundation.services.embedding import get_embedding_service

                return get_embedding_service().embed(text)
            embed_fn = make_mcp_embed_func(p)
            return run_async_blocking(embed_fn([text]))

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            if not texts:
                return []
            p = _ensure_port()
            if p <= 0:
                from omni.foundation.services.embedding import get_embedding_service

                return get_embedding_service().embed_batch(texts)
            embed_fn = make_mcp_embed_func(p)
            return run_async_blocking(embed_fn(texts))

    return _Wrapper()


_override_instance: Any = None


def _get_override_instance() -> Any:
    global _override_instance
    if _override_instance is None:
        _override_instance = _mcp_first_wrapper()
    return _override_instance


def _before_skill_execute() -> None:
    """Set embedding override so this execution uses MCP-first embedding (when not in MCP server)."""
    if os.environ.get("OMNI_EMBEDDING_CLIENT_ONLY"):
        return
    set_embedding_override(_get_override_instance())


def _after_skill_execute() -> None:
    """Clear embedding override after skill command finishes."""
    set_embedding_override(None)


def install_skill_embedding_override() -> None:
    """Register before/after skill execute hooks so CLI-invoked skills use MCP-first embedding."""
    from omni.foundation.skill_hooks import (
        register_after_skill_execute,
        register_before_skill_execute,
    )

    register_before_skill_execute(_before_skill_execute)
    register_after_skill_execute(_after_skill_execute)


__all__ = ["install_skill_embedding_override"]
