"""
agent/server.py - Agent MCP Handler (Thin Client)

Trinity Architecture - Agent Layer

This adapter is now a pure thin client that delegates all lifecycle
and execution management to the Core Kernel.

Logging: Uses Foundation layer (omni.foundation.config.logging)
"""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger

from omni.core.kernel import get_kernel
from omni.mcp.interfaces import MCPRequestHandler
from omni.mcp.types import (
    ErrorCode,
    JSONRPCRequest,
    JSONRPCResponse,
    make_error_response,
    make_success_response,
)

# Logger will be configured on first use via get_logger's lazy initialization
logger = get_logger("omni.agent.server")


class AgentMCPHandler(MCPRequestHandler):
    """
    Thin MCP Adapter for the Kernel.
    """

    def __init__(self):
        self._initialized = False
        self._verbose = False
        self._kernel = get_kernel()

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode before initialization."""
        self._verbose = verbose

    async def initialize(self) -> None:
        """Boot the Kernel when MCP handshake completes."""
        if self._initialized:
            return

        logger.info("🚀 [Agent] Booting Kernel...")

        # Delegate all lifecycle management to Kernel
        await self._kernel.initialize()

        # Ensure Kernel started successfully
        if not self._kernel.is_ready:
            logger.warning("⚠️ Kernel did not reach READY state, attempting start...")
            await self._kernel.start()

        # Enable hot reload by default
        self._kernel.enable_hot_reload()
        logger.info("👀 File watcher enabled for hot reload")

        self._initialized = True
        logger.info(
            f"✅ [Agent] Ready. Active skills: {len(self._kernel.skill_context.list_skills())}"
        )

    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Handle a JSON-RPC request."""
        if not self._initialized:
            await self.initialize()

        method = request.method
        params = request.params or {}

        try:
            if method == "initialize":
                return await self._handle_initialize(request)
            elif method == "tools/list":
                return await self._handle_list_tools(request)
            elif method == "tools/call":
                return await self._handle_call_tool(request)
            # Forward other methods or handle specifically
            elif method.startswith("resources/") or method.startswith("prompts/"):
                # Placeholder for future Kernel capabilities
                return make_success_response(request.id, {method.split("/")[0]: []})
            else:
                return make_error_response(
                    id=request.id,
                    code=ErrorCode.METHOD_NOT_FOUND,
                    message=f"Method not found: {method}",
                )

        except Exception as e:
            logger.error("❌ [MCP] Request error", error=str(e))
            return make_error_response(id=request.id, code=ErrorCode.INTERNAL_ERROR, message=str(e))

    async def handle_notification(self, method: str, params: Any) -> None:
        """Handle notifications from MCP client."""
        logger.debug(f"Received notification: {method}")
        if method == "notifications/state":
            # Client is notifying that its state has changed
            # Just acknowledge, no response needed for notifications
            logger.info("Client state notification received")
        # Add other notification handlers as needed

    async def _handle_initialize(self, request: JSONRPCRequest) -> JSONRPCResponse:
        await self.initialize()
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "omni-agent", "version": "2.0.0"},
                "capabilities": {
                    "tools": {"listChanged": True},  # Kernel supports dynamic loading
                },
            },
        )

    async def _handle_list_tools(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """List skills directly from Kernel Context."""
        context = self._kernel.skill_context
        tools = []

        # Iterate over all skills loaded by Kernel
        for skill_name in context.list_skills():
            skill = context.get_skill(skill_name)
            # UniversalScriptSkill uses list_commands() and get_command()
            if hasattr(skill, "list_commands") and callable(skill.list_commands):
                for cmd_name in skill.list_commands():
                    # Format tool name: skill.command
                    full_name = f"{skill_name}.{cmd_name}" if "." not in cmd_name else cmd_name

                    # Get command details
                    cmd = skill.get_command(cmd_name)
                    description = (
                        getattr(cmd, "description", f"Run {full_name}")
                        if cmd
                        else f"Run {full_name}"
                    )
                    # Ensure inputSchema has required "type": "object"
                    raw_schema = getattr(cmd, "input_schema", {}) if cmd else {}
                    input_schema = raw_schema.copy() if raw_schema else {}
                    if "type" not in input_schema:
                        input_schema["type"] = "object"

                    tools.append(
                        {
                            "name": full_name,
                            "description": description,
                            "inputSchema": input_schema,
                        }
                    )

        return make_success_response(request.id, {"tools": tools})

    async def _handle_call_tool(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Execute skill via Kernel Context."""
        params = request.params or {}
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if "." not in name:
            return make_error_response(
                request.id, ErrorCode.INVALID_PARAMS, "Tool name must be 'skill.command'"
            )

        skill_name, command_name = name.split(".", 1)

        skill = self._kernel.skill_context.get_skill(skill_name)
        if not skill:
            return make_error_response(
                request.id, ErrorCode.INVALID_PARAMS, f"Skill not found: {skill_name}"
            )

        try:
            result = await skill.execute(command_name, **arguments)
            return make_success_response(
                request.id, {"content": [{"type": "text", "text": str(result)}]}
            )
        except Exception as e:
            return make_error_response(request.id, ErrorCode.INTERNAL_ERROR, str(e))


def create_agent_handler() -> AgentMCPHandler:
    return AgentMCPHandler()


__all__ = ["AgentMCPHandler", "create_agent_handler"]
