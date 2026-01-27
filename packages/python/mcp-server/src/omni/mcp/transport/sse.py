"""
SSE (Server-Sent Events) Transport

Trinity Architecture - MCP Transport Layer

HTTP-based transport for web/cl browser clients.
Full MCP protocol support including async notifications.

Features:
- POST /message: Send JSON-RPC requests
- GET /events: Server-Sent Events stream for responses AND notifications
- Session management for notification delivery
- Request context for handlers to send notifications

Uses MCP SDK for JSON-RPC types.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

import orjson
import uvicorn
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from mcp.types import JSONRPCRequest, JSONRPCResponse

from omni.foundation.config.logging import get_logger

from ..interfaces import MCPRequestHandler

logger = get_logger("omni.mcp.sse")


def _create_queue() -> asyncio.Queue:
    """Factory for creating fresh asyncio.Queue instances."""
    return asyncio.Queue()


class SSESession(BaseModel):
    """SSE Session with notification queue."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    handler: MCPRequestHandler | None = None
    notification_queue: asyncio.Queue = Field(default_factory=_create_queue)
    connected: bool = True

    async def send_notification(self, method: str, params: dict | None = None) -> None:
        """Queue a notification to be sent to this session."""
        if not self.connected:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        await self.notification_queue.put(notification)
        logger.debug(f"Queued notification {method} for session {self.session_id}")

    def disconnect(self) -> None:
        """Mark session as disconnected."""
        self.connected = False
        # Cancel any waiting listeners
        try:
            self.notification_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


class SSESessionManager:
    """Manages SSE sessions and notification routing."""

    def __init__(self):
        self._sessions: dict[str, SSESession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, handler: MCPRequestHandler | None = None) -> SSESession:
        """Create a new SSE session."""
        async with self._lock:
            session_id = str(uuid.uuid4())[:8]
            session = SSESession(session_id=session_id, handler=handler)
            self._sessions[session_id] = session
            logger.info(f"SSE session created: {session_id}")
            return session

    async def get_session(self, session_id: str) -> SSESession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """Remove a session."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].disconnect()
                del self._sessions[session_id]
                logger.info(f"SSE session removed: {session_id}")

    async def broadcast_notification(self, method: str, params: dict | None = None) -> None:
        """Broadcast a notification to all connected sessions."""
        async with self._lock:
            sessions = list(self._sessions.values())

        for session in sessions:
            if session.connected:
                await session.send_notification(method, params)

    @property
    def active_sessions(self) -> int:
        """Get number of active sessions."""
        return len([s for s in self._sessions.values() if s.connected])


class SSEServer:
    """
    SSE-based MCP server for HTTP clients.

    Full MCP protocol support:
    - POST /message: Send JSON-RPC requests
    - GET /events: Server-Sent Events stream for responses AND notifications
    - Session management for notification delivery
    - Request context for handlers to send notifications

    Usage:
        from omni.mcp.interfaces import MCPRequestHandler
        from omni.mcp.transport.sse import SSEServer

        handler = MyHandler()
        server = SSEServer(handler, host="0.0.0.0", port=8080)
        await server.start()
    """

    def __init__(
        self,
        handler: MCPRequestHandler,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.handler = handler
        self.host = host
        self.port = port
        self._app: Starlette | None = None
        self._server: uvicorn.Server | None = None
        self._session_manager = SSESessionManager()

    def _create_app(self) -> Starlette:
        """Create the Starlette application."""

        async def handle_message(request: Request) -> Response:
            """Handle POST /message - receive JSON-RPC requests."""
            try:
                # Get session from query param
                session_id = request.query_params.get("session_id")
                session = None
                if session_id:
                    session = await self._session_manager.get_session(session_id)

                # Parse request body
                try:
                    body = await request.body()
                    data = orjson.loads(body)
                except orjson.JSONDecodeError:
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32700,
                                "message": "Invalid JSON",
                            },
                        },
                        status_code=400,
                    )

                # Cast to JSONRPCRequest (TypedDict doesn't support **kwargs)
                request_obj = cast(JSONRPCRequest, data)

                # Check if it's a notification (no id)
                msg_id = request_obj.get("id")
                is_notification = msg_id is None

                # Handle notification
                if is_notification:
                    await self.handler.handle_notification(
                        request_obj.get("method", ""),
                        request_obj.get("params"),
                    )
                    return JSONResponse({"jsonrpc": "2.0", "result": True})

                # Handle request
                response = await self.handler.handle_request(request_obj)

                # Handle both dict and Pydantic model responses
                if hasattr(response, "model_dump"):
                    response_dict: dict[str, Any] = response.model_dump()
                else:
                    response_dict = cast(dict[str, Any], response)

                # Build response
                resp_data: dict[str, Any] = {
                    "jsonrpc": response_dict.get("jsonrpc", "2.0"),
                    "id": response_dict.get("id"),
                }

                # Only include result or error, not both
                if response_dict.get("error") is not None:
                    resp_data["error"] = response_dict.get("error")
                elif "result" in response_dict:
                    resp_data["result"] = response_dict.get("result")

                return JSONResponse(resp_data)

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32603,
                            "message": str(e),
                        },
                    },
                    status_code=500,
                )

        async def events(request: Request) -> StreamingResponse:
            """GET /events - SSE stream for responses and notifications."""

            # Create session for this connection
            session = await self._session_manager.create_session(self.handler)
            session_id = session.session_id

            async def event_generator():
                """Generate SSE events for this session."""
                connected = session.connected

                # Send initial connection event
                yield f"data: {orjson.dumps({'type': 'connected', 'session_id': session_id}).decode()}\n\n".encode()

                try:
                    while connected and session.connected:
                        try:
                            # Wait for notification with timeout for ping
                            notification = await asyncio.wait_for(
                                session.notification_queue.get(),
                                timeout=25.0,  # Send ping every 25s
                            )

                            if notification is None:
                                # Session disconnected
                                break

                            # Send notification as SSE event
                            data = orjson.dumps(notification).decode()
                            yield f"data: {data}\n\n".encode()
                            logger.debug(f"Sent notification to session {session_id}")

                        except TimeoutError:
                            # Send ping to keep connection alive
                            yield f"data: {orjson.dumps({'type': 'ping'}).decode()}\n\n".encode()

                except asyncio.CancelledError:
                    logger.debug(f"SSE stream cancelled for session {session_id}")
                finally:
                    # Cleanup on disconnect
                    await self._session_manager.remove_session(session_id)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        async def health(request: Request) -> Response:
            """GET /health - Health check endpoint."""
            return JSONResponse(
                {
                    "status": "healthy",
                    "active_sessions": self._session_manager.active_sessions,
                }
            )

        async def ready(request: Request) -> Response:
            """GET /ready - Readiness check."""
            return JSONResponse(
                {
                    "status": "ready",
                    "sessions": self._session_manager.active_sessions,
                }
            )

        routes = [
            Route("/message", handle_message, methods=["POST"]),
            Route("/events", events),
            Route("/health", health),
            Route("/ready", ready),
        ]

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ]

        return Starlette(routes=routes, middleware=middleware)

    @property
    def is_connected(self) -> bool:
        """Check if server is running."""
        return self._server is not None and not self._server.should_exit

    async def start(self) -> None:
        """Start the SSE server."""
        logger.info(f"Starting SSE server on {self.host}:{self.port}...")
        self._app = self._create_app()

        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        # Configure uvicorn access log to reduce noise
        import logging

        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

        await self._server.serve()

    async def stop(self) -> None:
        """Stop the SSE server."""
        logger.info("Stopping SSE server...")
        if self._server:
            self._server.should_exit = True

        # Disconnect all sessions
        async with self._session_manager._lock:
            for session_id in list(self._session_manager._sessions.keys()):
                await self._session_manager.remove_session(session_id)

        logger.info("SSE server stopped")

    async def broadcast_notification(self, method: str, params: dict | None = None) -> None:
        """Broadcast a notification to all connected clients."""
        await self._session_manager.broadcast_notification(method, params)

    async def send_notification_to_session(
        self,
        session_id: str,
        method: str,
        params: dict | None = None,
    ) -> bool:
        """Send a notification to a specific session."""
        session = await self._session_manager.get_session(session_id)
        if session:
            await session.send_notification(method, params)
            return True
        return False


__all__ = ["SSEServer", "SSESession", "SSESessionManager"]
