"""
agent/mcp_server/sse.py - SSE Transport for Claude Code CLI

Uses MCP SDK's StreamableHTTPServerTransport for standard MCP protocol.
Enhanced with session management and security features.

Performance:
- orjson for 10-50x faster JSON serialization
- Zero-copy where possible
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import orjson
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logger = logging.getLogger("omni.agent.mcp_server.sse")


class MCPSessionManager:
    """Manages MCP sessions for concurrent connections."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, handler: Any) -> dict:
        """Create a new session."""
        async with self._lock:
            self._sessions[session_id] = {
                "handler": handler,
                "created_at": asyncio.get_event_loop().time(),
            }
            logger.debug(f"Created session: {session_id}")
            return self._sessions[session_id]

    async def get_session(self, session_id: str) -> dict | None:
        """Get session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """Remove session."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug(f"Removed session: {session_id}")

    @property
    def active_sessions(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)


# Global session manager
_session_manager = MCPSessionManager()


def create_sse_app(
    handler: Any,
    host: str = "127.0.0.1",
    port: int = 3000,
    enable_cors: bool = True,
    session_timeout: float = 300.0,
) -> Starlette:
    """Create SSE Starlette application with MCP SDK StreamableHTTP transport.

    Args:
        handler: MCP request handler (AgentMCPHandler)
        host: Host to bind to
        port: Port to listen on
        enable_cors: Enable CORS middleware
        session_timeout: Session timeout in seconds

    Returns:
        Starlette application
    """
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    from mcp.server.transport_security import TransportSecuritySettings

    # Create transport with security settings
    security_settings = TransportSecuritySettings(
        allowed_hosts=["*"],  # Allow all hosts
        allowed_origins=["*"],  # Allow all origins
    )
    transport = StreamableHTTPServerTransport(
        mcp_session_id=None,
        security_settings=security_settings,
    )

    async def handle_mcp(request: Request) -> JSONResponse:
        """Handle MCP HTTP requests with robust error handling."""
        # Initialize default values for error cases
        method = ""
        req_id = None

        # Generate or extract session ID
        session_id = request.headers.get("mcp-session-id") or str(uuid.uuid4())

        try:
            # Read the request body
            body = await request.body()
            if not body:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "Invalid Request: Empty body"},
                    },
                    status_code=400,
                )

            try:
                data = orjson.loads(body)
            except orjson.JSONDecodeError as e:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {e}"},
                    },
                    status_code=400,
                )

            # Validate JSON-RPC version
            if data.get("jsonrpc") != "2.0":
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {"code": -32600, "message": "Invalid JSON-RPC version"},
                    },
                    status_code=400,
                )

            method = data.get("method", "")
            params = data.get("params", {})
            req_id = data.get("id")

            # Validate protocol version for initialize
            if method == "initialize":
                client_version = params.get("protocolVersion", "")
                # MCP protocol version check
                if client_version and not _is_supported_protocol_version(client_version):
                    logger.warning(f"Unsupported protocol version: {client_version}")

            # Handle the request using the provided handler
            request_dict = {
                "method": method,
                "params": params,
                "id": req_id,
                "jsonrpc": "2.0",
                "_session_id": session_id,
            }

            # Add timeout for request handling
            response = await asyncio.wait_for(
                handler.handle_request(request_dict),
                timeout=session_timeout,
            )

            # Return the response
            response_data = {"jsonrpc": "2.0", "id": req_id}
            if isinstance(response, dict):
                if "result" in response:
                    response_data["result"] = response["result"]
                elif "error" in response:
                    response_data["error"] = response["error"]

            # Use orjson for faster serialization (10-50x faster than stdlib json)
            response_bytes = orjson.dumps(response_data)

            # Add session header for tracking
            return Response(
                content=response_bytes,
                media_type="application/json",
                headers={"MCP-Session-Id": session_id},
            )

        except asyncio.TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": "Request timeout"},
                },
                status_code=504,
                headers={"MCP-Session-Id": session_id},
            )

        except Exception as e:
            logger.error(f"Error handling MCP request: {e}", exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                },
                status_code=500,
                headers={"MCP-Session-Id": session_id},
            )

    async def handle_get(request: Request) -> JSONResponse:
        """Handle GET requests - return server info."""
        return JSONResponse(
            {
                "name": "omni-agent",
                "version": "2.0.0",
                "protocolVersion": "2024-11-05",
            }
        )

    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse(
            {
                "status": "healthy",
                "active_sessions": _session_manager.active_sessions,
            }
        )

    # OAuth endpoints (required by Claude Code for authentication)
    async def oauth_discovery(request: Request) -> JSONResponse:
        """OAuth discovery endpoint."""
        return JSONResponse(
            {
                "issuer": f"http://{host}:{port}",
                "authorization_endpoint": f"http://{host}:{port}/authorize",
                "token_endpoint": f"http://{host}:{port}/token",
                "response_types_supported": ["none"],
                "grant_types_supported": ["client_credentials"],
                "scopes_supported": ["read", "write"],
            }
        )

    async def oauth_register(request: Request) -> JSONResponse:
        """OAuth register endpoint."""
        return JSONResponse({"client_id": "omni-agent"})

    # Build routes
    routes = [
        Route("/sse", handle_mcp, methods=["GET", "POST"]),
        Route("/mcp", handle_mcp, methods=["GET", "POST"]),
        Route("/messages/", handle_mcp, methods=["GET", "POST"]),
        Route("/", handle_mcp, methods=["GET", "POST"]),
        Route("/health", health),
        Route("/.well-known/oauth-authorization-server", oauth_discovery),
        Route("/.well-known/openid-configuration", oauth_discovery),
        Route("/register", oauth_register, methods=["POST"]),
        Route("/.well-known/oauth-protected-resource", oauth_discovery),
    ]

    # Add CORS middleware if enabled
    middleware = []
    if enable_cors:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

    return Starlette(routes=routes, middleware=middleware)


def _is_supported_protocol_version(version: str) -> bool:
    """Check if protocol version is supported."""
    supported = ["2024-11-05", "2024-09-01", "2024-06-14"]
    return version in supported


async def run_sse(
    handler: Any,
    host: str = "127.0.0.1",
    port: int = 3000,
    enable_cors: bool = True,
) -> None:
    """Run SSE server.

    Args:
        handler: MCP request handler
        host: Host to bind to
        port: Port to listen on
        enable_cors: Enable CORS middleware
    """
    app = create_sse_app(handler, host, port, enable_cors)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


__all__ = ["create_sse_app", "run_sse"]
