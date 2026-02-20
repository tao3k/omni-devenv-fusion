"""Session manager for MCP SSE transport."""

from __future__ import annotations

import asyncio
from typing import Any

import logging

logger = logging.getLogger("omni.agent.mcp_server.sse")


class MCPSessionManager:
    """Manages MCP sessions for concurrent connections."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, handler: Any) -> dict[str, Any]:
        """Create a new session."""
        async with self._lock:
            self._sessions[session_id] = {
                "handler": handler,
                "created_at": asyncio.get_event_loop().time(),
            }
            logger.debug("Created session: %s", session_id)
            return self._sessions[session_id]

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """Remove session."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug("Removed session: %s", session_id)

    @property
    def active_sessions(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)
