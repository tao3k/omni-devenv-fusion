"""
agent/mcp_server.py
 MCP Server Entry Point

Legacy entry point - delegates to agent.mcp_server module.
Use `from agent.mcp_server import run` for direct imports.
"""

from __future__ import annotations

# Re-export for backward compatibility
from agent.mcp_server import run, server_lifespan, run_stdio, run_sse

__all__ = ["run", "server_lifespan", "run_stdio", "run_sse"]
