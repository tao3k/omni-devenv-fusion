"""
omni.mcp - High-Performance MCP Transport Layer

Pure transport implementation. No business logic.

Modules:
    types: JSON-RPC message definitions and MCP error codes
    interfaces: Protocol definitions for dependency inversion
    server: Generic MCP server orchestration
    transport: Transport implementations (stdio, sse)
"""

from .interfaces import MCPRequestContext, MCPRequestHandler, MCPSession, MCPTransport
from .server import MCPServer
from .types import (
    ErrorCode,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPErrorCode,
    make_error_response,
    make_mcp_error_response,
    make_success_response,
)

__all__ = [
    # Types
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "make_error_response",
    "make_success_response",
    "make_mcp_error_response",
    "ErrorCode",
    "MCPErrorCode",
    # Interfaces
    "MCPRequestHandler",
    "MCPTransport",
    "MCPSession",
    "MCPRequestContext",
    # Server
    "MCPServer",
]

__version__ = "0.2.0"
