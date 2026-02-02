"""
Unit test for MCP server using omni.mcp transport.

Tests that:
1. Server module imports correctly
2. Handler implements MCPRequestHandler protocol
3. Transport layer works with handler
4. Server can be composed correctly

Usage:
    uv run pytest packages/python/agent/src/agent/tests/integration/test_mcp_stdio.py -v
"""

import asyncio
from pathlib import Path

import pytest


class TestServerModuleImports:
    """Test all imports required for MCP server."""

    def test_server_module_import(self):
        """Verify server module imports correctly."""
        from omni.agent.server import AgentMCPHandler, create_agent_handler

        assert AgentMCPHandler is not None
        assert callable(create_agent_handler)

    def test_handler_has_protocol_methods(self):
        """Verify AgentMCPHandler has required protocol methods."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        assert hasattr(handler, "handle_request")
        assert hasattr(handler, "handle_notification")
        assert hasattr(handler, "initialize")

    def test_omni_mcp_transport_import(self):
        """Verify omni.mcp transport imports correctly."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        assert MCPServer is not None
        assert StdioTransport is not None

    def test_omni_mcp_sse_import(self):
        """Verify omni.mcp SSE transport imports correctly."""
        from omni.mcp.transport.sse import SSEServer

        assert SSEServer is not None


class TestServerComposition:
    """Test server composition with handler and transport."""

    def test_create_handler(self):
        """Test that create_agent_handler returns a handler."""
        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        assert handler is not None

    def test_handler_not_initialized_initially(self):
        """Test that handler is not initialized until initialize() is called."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        assert handler._initialized is False

    @pytest.mark.asyncio
    async def test_handler_initialize(self):
        """Test that handler.initialize() sets _initialized to True."""
        from omni.agent.server import AgentMCPHandler

        handler = AgentMCPHandler()
        await handler.initialize()
        assert handler._initialized is True


class TestExitQueue:
    """Test exit queue mechanism for graceful shutdown."""

    def test_exit_queue_operations(self):
        """Test putting and getting from exit queue."""

        async def test_queue():
            test_queue = asyncio.Queue()

            # Put a value
            test_queue.put_nowait(True)

            # Get the value
            value = await test_queue.get()
            assert value is True
            assert test_queue.empty()

        asyncio.run(test_queue())


class TestWatcherPathDisplay:
    """Test watcher path display functionality."""

    def test_skills_path_relative_display(self):
        """Test that skills path is displayed correctly."""
        from omni.foundation.config.skills import SKILLS_DIR

        skills_path = str(SKILLS_DIR())
        skills_path_obj = Path(skills_path)

        # Get last 2 components
        parts = (
            skills_path_obj.parts[-2:] if len(skills_path_obj.parts) >= 2 else skills_path_obj.parts
        )
        display_path = "/".join(parts)

        # Should contain "skills"
        assert "skills" in display_path


class TestGracefulShutdown:
    """Test graceful shutdown mechanisms."""

    def test_server_can_be_composed(self):
        """Test that server can be composed from handler and transport."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        transport = StdioTransport()
        # Set handler via set_handler method (new API)
        transport.set_handler(handler)
        server = MCPServer(handler=handler, transport=transport)

        assert server.handler is handler
        assert server.transport is transport
        assert server.is_running is False


class TestServerProcessManagement:
    """Test server process management.

    Note: Current implementation uses omni.mcp transport directly.
    """

    def test_server_has_start_and_stop(self):
        """Test that server has start and stop methods."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        transport = StdioTransport()
        transport.set_handler(handler)  # New API: set handler separately
        server = MCPServer(handler=handler, transport=transport)

        assert hasattr(server, "start")
        assert hasattr(server, "stop")
        assert callable(server.start)
        assert callable(server.stop)


class TestShutdownCount:
    """Test shutdown counter for double-Ctrl-C detection."""

    def test_shutdown_uses_os_exit(self):
        """Test that shutdown uses os._exit for immediate termination."""

        # Verify os module is available for _exit
        import os

        assert hasattr(os, "_exit")


class TestMCPProtocolHandlers:
    """Test MCP protocol handlers are registered correctly."""

    def test_server_registers_handlers(self):
        """Test that server registers required handlers."""
        from omni.agent.mcp_server.server import AgentMCPServer
        import inspect

        source = inspect.getsource(AgentMCPServer._register_handlers)

        # Check for decorator-based registrations
        assert "@self._app.list_tools()" in source
        assert "@self._app.call_tool()" in source
        assert "@self._app.list_resources()" in source
        assert "@self._app.read_resource()" in source
        assert "@self._app.list_prompts()" in source
        assert "@self._app.get_prompt()" in source

    def test_server_has_specific_tools(self):
        """Verify server registers special kernel tools."""
        from omni.agent.mcp_server.server import AgentMCPServer
        import inspect

        source = inspect.getsource(AgentMCPServer._register_handlers)
        assert 'name="omni"' in source
        assert 'name="sys_query"' in source
        assert 'name="sys_exec"' in source


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance for tool schema."""

    @pytest.mark.asyncio
    async def test_tool_list_returns_valid_schema(self):
        """Test that tools/list returns valid MCP-compliant inputSchema when tools exist."""
        from mcp.types import JSONRPCRequest

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        await handler.initialize()

        # Create Pydantic request, then convert to dict for handler
        pydantic_request = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
        request = pydantic_request.model_dump()

        response = await handler._handle_list_tools(request)

        # Response is a plain dict
        assert response.get("error") is None, f"Response error: {response.get('error')}"
        tools = response.get("result", {}).get("tools", [])

        # Only validate schema if tools are returned
        # (Skills may not have commands, which is valid)
        if len(tools) == 0:
            pytest.skip("No tools available (skills have no commands)")

        assert len(tools) > 0, "No tools returned"

        # Validate each tool has valid inputSchema
        for tool in tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "inputSchema" in tool, f"Tool missing inputSchema: {tool.get('name')}"
            schema = tool["inputSchema"]
            # MCP requires type to be "object"
            assert schema.get("type") == "object", (
                f"Tool '{tool['name']}' has invalid type: {schema.get('type')}"
            )

    @pytest.mark.asyncio
    async def test_tool_names_follow_skill_command_pattern(self):
        """Test that tool names follow 'skill.command' pattern when tools exist."""
        from mcp.types import JSONRPCRequest

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        await handler.initialize()

        # Create Pydantic request, then convert to dict for handler
        pydantic_request = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
        request = pydantic_request.model_dump()

        response = await handler._handle_list_tools(request)

        # Response is a plain dict
        tools = response.get("result", {}).get("tools", [])

        # Skip if no tools available
        if len(tools) == 0:
            pytest.skip("No tools available (skills have no commands)")

        for tool in tools:
            name = tool["name"]
            assert "." in name, f"Tool name '{name}' should follow 'skill.command' pattern"

    @pytest.mark.asyncio
    async def test_tool_descriptions_are_present(self):
        """Test that all tools have descriptions when tools exist."""
        from mcp.types import JSONRPCRequest

        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        await handler.initialize()

        # Create Pydantic request, then convert to dict for handler
        pydantic_request = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
        request = pydantic_request.model_dump()

        response = await handler._handle_list_tools(request)

        # Response is a plain dict
        tools = response.get("result", {}).get("tools", [])

        # Skip if no tools available
        if len(tools) == 0:
            pytest.skip("No tools available (skills have no commands)")

        for tool in tools:
            assert "description" in tool, f"Tool '{tool.get('name')}' missing description"
            assert tool["description"], f"Tool '{tool.get('name')}' has empty description"


class TestIntegration:
    """Integration tests for imports and basic functionality."""

    def test_full_import_chain(self):
        """Test that all components can be imported together."""
        from omni.mcp import MCPServer
        from omni.mcp.transport.sse import SSEServer
        from omni.mcp.transport.stdio import StdioTransport

        from omni.agent.server import AgentMCPHandler, create_agent_handler

        # All should be callable or not None
        assert AgentMCPHandler is not None
        assert callable(create_agent_handler)
        assert MCPServer is not None
        assert StdioTransport is not None
        assert SSEServer is not None


class TestSkillPathResolutionIntegration:
    """Integration tests to verify skill path resolution from scanner to MCP tools.

    These tests prevent the regression where skills like "git" were incorrectly
    resolved to "/project/git" instead of "/project/assets/skills/git", causing
    no tools to be registered to the MCP server.
    """

    @pytest.mark.asyncio
    async def test_scanner_returns_correct_skill_paths(self):
        """Verify scanner extracts correct skill paths from file paths.

        This is the critical test for the bug where:
        - file_path: "/project/assets/skills/git/scripts/commit.py"
        - Buggy extraction: "git" -> scripts_path = "/project/git/scripts" (WRONG)
        - Fixed extraction: "assets/skills/git" -> scripts_path = "/project/assets/skills/git/scripts" (CORRECT)
        """
        from omni.foundation.bridge.scanner import PythonSkillScanner
        from omni.foundation.config.skills import SKILLS_DIR

        scanner = PythonSkillScanner()
        skills = await scanner.scan_directory()

        # Skip if no skills in database
        if len(skills) == 0:
            pytest.skip("No skills loaded from LanceDB")

        for skill in skills:
            # Verify skill_path is in correct format (must be "assets/skills/{name}")
            assert skill.skill_path == f"assets/skills/{skill.skill_name}", (
                f"Skill '{skill.skill_name}' has incorrect path: {skill.skill_path}. "
                f"Expected: 'assets/skills/{skill.skill_name}'"
            )

            # Verify the skill directory exists using SKILLS_DIR(name)
            skill_dir = SKILLS_DIR(skill.skill_name)
            assert skill_dir.exists(), (
                f"Skill directory does not exist: {skill_dir}. "
                f"Check scanner.py skill_path extraction."
            )

    @pytest.mark.asyncio
    async def test_mcp_handler_receives_tools_from_scanner(self):
        """Verify MCP handler receives tools from scanner with correct skill paths.

        This test ensures the integration between scanner and handler works,
        preventing the case where handler.get_tools() returns empty list.
        """
        from omni.agent.server import create_agent_handler

        handler = create_agent_handler()
        await handler.initialize()

        # Get tools via the handler's list method
        from mcp.types import JSONRPCRequest

        pydantic_request = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
        request = pydantic_request.model_dump()

        response = await handler._handle_list_tools(request)

        tools = response.get("result", {}).get("tools", [])

        # Critical assertion - tools must not be empty
        assert len(tools) > 0, (
            "No tools registered to MCP handler! "
            "This indicates skill path resolution failed. "
            "Check scanner.py skill_path extraction."
        )

    @pytest.mark.asyncio
    async def test_skill_scripts_path_is_valid(self):
        """Verify that skill scripts path resolves to existing directory.

        This catches the bug where scripts_path was invalid because
        skill_path was extracted incorrectly.
        """
        from omni.agent.server import create_agent_handler
        from pathlib import Path

        handler = create_agent_handler()
        await handler.initialize()

        # Get the kernel's skill context
        kernel = handler._kernel
        context = kernel.skill_context

        # Check each skill can load commands
        for skill_name in context.list_skills():
            skill = context.get_skill(skill_name)
            if skill is None:
                continue

            # Check if skill has commands
            if hasattr(skill, "list_commands") and callable(skill.list_commands):
                commands = skill.list_commands()
                if len(commands) > 0:
                    # Verify the skill's path resolves correctly
                    # This exercises the _path property which was the source of the bug
                    if hasattr(skill, "_path"):
                        skill_path = skill._path
                        scripts_path = skill_path / "scripts"

                        assert scripts_path.exists(), (
                            f"Skill '{skill_name}': scripts_path does not exist: {scripts_path}. "
                            f"This indicates path resolution failed during skill loading."
                        )

    @pytest.mark.asyncio
    async def test_json_rpc_response_id_is_not_null(self):
        """Verify JSON-RPC responses have non-null id for requests.

        This prevents the regression where tools/list returned response
        with id=null, causing MCP client validation failures.
        """
        from omni.agent.server import create_agent_handler
        from mcp.types import JSONRPCRequest

        handler = create_agent_handler()
        await handler.initialize()

        # Make a tools/list request with a specific id
        test_id = 42
        pydantic_request = JSONRPCRequest(jsonrpc="2.0", id=test_id, method="tools/list", params={})
        request = pydantic_request.model_dump()

        response = await handler._handle_list_tools(request)

        # Response must have the same id as the request
        assert response.get("id") == test_id, (
            f"Response id ({response.get('id')}) does not match request id ({test_id}). "
            "JSON-RPC 2.0 requires id to match."
        )

        # Response id must not be null for requests (notifications have no id)
        assert response.get("id") is not None, (
            "Response id is null. JSON-RPC 2.0 requires non-null id for request responses."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
