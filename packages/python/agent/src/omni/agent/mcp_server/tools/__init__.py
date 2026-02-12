"""
MCP Server Tools

Modular tool definitions for the Agent MCP Server.

Modules:
- embedding: Embedding generation via preloaded model
- tracer: Execution tracing (UltraRAG-style)
"""

from .embedding import register_embedding_tools
from .tracer import register_tracer_tools

__all__ = [
    "register_embedding_tools",
    "register_tracer_tools",
]
