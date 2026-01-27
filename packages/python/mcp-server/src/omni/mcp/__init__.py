"""
omni.mcp - High-Performance MCP Transport Layer

Trinity Architecture - Transport Layer

Pure transport implementation. No business logic.

Uses MCP SDK types for JSON-RPC compliance (type hints only).

Modules:
    interfaces: Protocol definitions for dependency inversion
    server: Generic MCP server orchestration
    transport: Transport implementations (stdio, sse)
"""

from .interfaces import MCPRequestContext, MCPRequestHandler, MCPSession, MCPTransport
from .server import MCPServer
from .transport.sse import SSEServer, SSESession, SSESessionManager
from .transport.stdio import StdioTransport

__all__ = [
    # Interfaces
    "MCPRequestContext",
    "MCPRequestHandler",
    "MCPSession",
    "MCPTransport",
    # Server
    "MCPServer",
    # Transport
    "StdioTransport",
    "SSEServer",
    "SSESession",
    "SSESessionManager",
]

__version__ = "0.4.0"
