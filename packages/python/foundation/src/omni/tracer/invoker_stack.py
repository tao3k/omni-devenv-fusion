"""
invoker_stack.py - Helpers for building standard ToolInvoker stacks.
"""

from __future__ import annotations

from typing import Any

from .composite_invoker import CompositeToolInvoker
from .mcp_invoker import MCPToolInvoker
from .node_factory import MappingToolInvoker, NoOpToolInvoker, ToolInvoker
from .retrieval_invoker import RetrievalToolInvoker


def create_default_invoker_stack(
    *,
    mcp_client: Any | None = None,
    mapping: dict[str, Any] | None = None,
    include_retrieval: bool = True,
    retrieval_default_backend: str = "lance",
    default_invoker: ToolInvoker | None = None,
) -> CompositeToolInvoker:
    """Build the default invoker stack in priority order.

    Order:
    1. MCPToolInvoker (if `mcp_client` is provided)
    2. RetrievalToolInvoker (if `include_retrieval` is True)
    3. MappingToolInvoker (if mapping is provided)
    4. default_invoker (or NoOpToolInvoker)
    """
    chain: list[ToolInvoker] = []
    if mcp_client is not None:
        chain.append(MCPToolInvoker(mcp_client))
    if include_retrieval:
        chain.append(RetrievalToolInvoker(default_backend=retrieval_default_backend))
    if mapping:
        chain.append(MappingToolInvoker(mapping))

    return CompositeToolInvoker(
        chain,
        default_invoker=default_invoker or NoOpToolInvoker(),
    )


__all__ = [
    "create_default_invoker_stack",
]
