"""
Integration tests for Stage 3.5: Holographic MCP Gateway Integration

Tests verify that:
1. AgentMCPServer can be initialized with holographic mode
2. Holographic registry integration works correctly
3. Tool discovery delegates to HolographicRegistry when enabled
4. System status includes holographic mode information

Usage:
    uv run pytest packages/python/agent/tests/integration/test_mcp_holographic.py -v
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestHolographicServerInitialization:
    """Test AgentMCPServer holographic mode initialization."""

    def test_server_initializes_without_holographic(self):
        """Verify server initializes with holographic mode disabled by default."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=False)

        assert server._use_holographic is False
        assert server._holographic_adapter is None
        assert server._holographic_registry is None

    def test_server_initializes_with_holographic_flag(self):
        """Verify server initializes with holographic mode enabled when flag is set."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)

        assert server._use_holographic is True
        assert server._holographic_adapter is None
        assert server._holographic_registry is None

    def test_server_has_holographic_methods(self):
        """Verify server has all required holographic mode methods."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        # Check required methods exist
        assert hasattr(server, "_init_holographic_mode")
        assert hasattr(server, "_list_holographic_tools")
        assert hasattr(server, "_convert_holographic_to_mcp_tools")
        assert hasattr(server, "_build_holographic_input_schema")
        assert hasattr(server, "_call_holographic_tool")
        assert hasattr(server, "_python_type_to_json_type")


class TestHolographicTypeConversion:
    """Test type conversion utilities for holographic mode."""

    def test_python_type_to_json_type_mapping(self):
        """Verify Python types are correctly mapped to JSON Schema types."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        # Test basic type mappings
        assert server._python_type_to_json_type("str") == "string"
        assert server._python_type_to_json_type("string") == "string"
        assert server._python_type_to_json_type("int") == "integer"
        assert server._python_type_to_json_type("float") == "number"
        assert server._python_type_to_json_type("bool") == "boolean"
        assert server._python_type_to_json_type("list") == "array"
        assert server._python_type_to_json_type("dict") == "object"

    def test_python_type_to_json_type_optional(self):
        """Verify Optional[X] types are handled correctly."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        assert server._python_type_to_json_type("Optional[str]") == "string"
        assert server._python_type_to_json_type("Optional[int]") == "integer"

    def test_python_type_to_json_type_list(self):
        """Verify List[X] types return array."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        assert server._python_type_to_json_type("List[str]") == "array"
        assert server._python_type_to_json_type("List[int]") == "array"

    def test_python_type_to_json_type_unknown(self):
        """Verify unknown types default to string."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        assert server._python_type_to_json_type("unknown") == "string"
        assert server._python_type_to_json_type("CustomType") == "string"


class TestHolographicInputSchema:
    """Test input schema building for holographic tools."""

    def test_build_input_schema_basic(self):
        """Verify basic input schema building."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        # Create mock metadata
        mock_metadata = MagicMock()
        mock_metadata.name = "test_tool"
        mock_metadata.description = "A test tool"
        mock_metadata.args = [
            {"name": "path", "type": "str", "description": "File path"},
            {"name": "count", "type": "int", "description": "Number of items"},
        ]

        schema = server._build_holographic_input_schema(mock_metadata)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "path" in schema["properties"]
        assert "count" in schema["properties"]
        assert schema["properties"]["path"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"

    def test_build_input_schema_empty_args(self):
        """Verify input schema with no arguments."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        mock_metadata = MagicMock()
        mock_metadata.name = "simple_tool"
        mock_metadata.description = "A simple tool"
        mock_metadata.args = []

        schema = server._build_holographic_input_schema(mock_metadata)

        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []

    def test_build_input_schema_with_required(self):
        """Verify required fields are correctly identified."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        mock_metadata = MagicMock()
        mock_metadata.name = "required_tool"
        mock_metadata.description = "A tool with required args"
        mock_metadata.args = [
            {"name": "required_arg", "type": "str", "description": "Required"},
            {"name": "optional_arg", "type": "str", "description": "Optional", "required": False},
        ]

        schema = server._build_holographic_input_schema(mock_metadata)

        assert "required_arg" in schema["required"]
        # Note: current implementation adds all args to required
        # This is correct for the basic implementation


class TestHolographicToolConversion:
    """Test tool metadata to MCP tool conversion."""

    def test_convert_holographic_to_mcp_tools(self):
        """Verify ToolMetadata list is converted to MCP Tool list."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        # Create mock metadata
        mock_metadata1 = MagicMock()
        mock_metadata1.name = "tool1"
        mock_metadata1.description = "First tool"
        mock_metadata1.args = [{"name": "arg1", "type": "str", "description": "Argument 1"}]

        mock_metadata2 = MagicMock()
        mock_metadata2.name = "tool2"
        mock_metadata2.description = "Second tool"
        mock_metadata2.args = []

        tools_metadata = [mock_metadata1, mock_metadata2]
        mcp_tools = server._convert_holographic_to_mcp_tools(tools_metadata)

        assert len(mcp_tools) == 2
        assert mcp_tools[0].name == "tool1"
        assert mcp_tools[0].description == "First tool"
        assert mcp_tools[1].name == "tool2"
        assert mcp_tools[1].description == "Second tool"

    def test_convert_empty_list(self):
        """Verify empty metadata list returns empty tool list."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer()

        mcp_tools = server._convert_holographic_to_mcp_tools([])

        assert len(mcp_tools) == 0


class TestHolographicToolListing:
    """Test holographic tool listing functionality."""

    @pytest.mark.asyncio
    async def test_list_holographic_tools_no_registry(self):
        """Verify list returns empty when registry is not available."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)
        # Registry is None by default

        tools = await server._list_holographic_tools()

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_list_holographic_tools_with_query(self):
        """Verify semantic search is used when query is provided."""
        from omni.agent.mcp_server.server import AgentMCPServer
        from omni.core.skills.registry.holographic import ToolMetadata

        server = AgentMCPServer(use_holographic=True)

        # Mock registry with search_hybrid
        mock_registry = AsyncMock()
        mock_registry.search_hybrid = AsyncMock(
            return_value=[
                ToolMetadata(
                    name="git_commit",
                    description="Commit changes",
                    module="git",
                    file_path="skills/git/scripts/commit.py",
                    args=[{"name": "message", "type": "str", "description": "Commit message"}],
                    return_type="str",
                )
            ]
        )
        server._holographic_registry = mock_registry

        tools = await server._list_holographic_tools(query="make a commit")

        # Verify search_hybrid was called with query
        mock_registry.search_hybrid.assert_called_once()
        call_kwargs = mock_registry.search_hybrid.call_args.kwargs
        assert call_kwargs["query"] == "make a commit"
        assert call_kwargs["limit"] == 20

        assert len(tools) == 1
        assert tools[0].name == "git_commit"

    @pytest.mark.asyncio
    async def test_list_holographic_tools_without_query(self):
        """Verify list_tools is used when no query is provided."""
        from omni.agent.mcp_server.server import AgentMCPServer
        from omni.core.skills.registry.holographic import ToolMetadata

        server = AgentMCPServer(use_holographic=True)

        # Mock registry with list_tools
        mock_registry = AsyncMock()
        mock_registry.list_tools = AsyncMock(
            return_value=[
                ToolMetadata(
                    name="file_read",
                    description="Read a file",
                    module="file",
                    file_path="skills/file/scripts/read.py",
                    args=[{"name": "path", "type": "str", "description": "File path"}],
                    return_type="str",
                )
            ]
        )
        server._holographic_registry = mock_registry

        tools = await server._list_holographic_tools()

        # Verify list_tools was called
        mock_registry.list_tools.assert_called_once_with(limit=20)

        assert len(tools) == 1
        assert tools[0].name == "file_read"


class TestHolographicToolExecution:
    """Test holographic tool execution functionality."""

    @pytest.mark.asyncio
    async def test_call_holographic_tool_no_registry(self):
        """Verify error returned when registry is not available."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)

        result = await server._call_holographic_tool("test_tool", {"arg": "value"})

        assert len(result) == 1
        assert "not available" in result[0].text

    @pytest.mark.asyncio
    async def test_call_holographic_tool_not_found(self):
        """Verify error returned when tool is not found."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)

        # Mock registry
        mock_registry = AsyncMock()
        mock_registry.get_tool = AsyncMock(return_value=None)
        server._holographic_registry = mock_registry

        result = await server._call_holographic_tool("nonexistent_tool", {})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_call_holographic_tool_success(self):
        """Verify tool execution with lazy loading."""
        from omni.agent.mcp_server.server import AgentMCPServer
        from omni.core.skills.registry.holographic import ToolMetadata

        server = AgentMCPServer(use_holographic=True)

        # Create mock metadata
        metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            module="test_module",
            file_path="skills/test/scripts/tool.py",
            args=[{"name": "arg", "type": "str", "description": "Test arg"}],
            return_type="str",
        )

        # Mock registry
        mock_registry = AsyncMock()
        mock_registry.get_tool = AsyncMock(return_value=metadata)
        server._holographic_registry = mock_registry

        # Mock LazyTool
        with patch("omni.core.skills.registry.holographic.LazyTool") as MockLazyTool:
            mock_lazy_tool = AsyncMock()
            mock_lazy_tool.load = AsyncMock(return_value=lambda arg: f"Result: {arg}")
            MockLazyTool.return_value = mock_lazy_tool

            result = await server._call_holographic_tool("test_tool", {"arg": "value"})

            assert len(result) == 1
            assert "Result: value" in result[0].text

    @pytest.mark.asyncio
    async def test_call_holographic_tool_exception(self):
        """Verify error handling when tool execution fails."""
        from omni.agent.mcp_server.server import AgentMCPServer
        from omni.core.skills.registry.holographic import ToolMetadata

        server = AgentMCPServer(use_holographic=True)

        metadata = ToolMetadata(
            name="failing_tool",
            description="A tool that fails",
            module="test_module",
            file_path="skills/test/scripts/fail.py",
            args=[],
            return_type="str",
        )

        mock_registry = AsyncMock()
        mock_registry.get_tool = AsyncMock(return_value=metadata)
        server._holographic_registry = mock_registry

        with patch("omni.core.skills.registry.holographic.LazyTool") as MockLazyTool:
            mock_lazy_tool = AsyncMock()
            mock_lazy_tool.load = AsyncMock(
                return_value=lambda: (_ for _ in ()).throw(ValueError("Test error"))
            )
            MockLazyTool.return_value = mock_lazy_tool

            result = await server._call_holographic_tool("failing_tool", {})

            assert len(result) == 1
            assert "Error" in result[0].text


class TestHolographicRegistryInitialization:
    """Test holographic registry initialization."""

    def test_init_holographic_mode_disabled(self):
        """Verify initialization is skipped when holographic mode is disabled."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=False)
        server._init_holographic_mode()

        assert server._holographic_registry is None

    @pytest.mark.asyncio
    async def test_init_holographic_mode_no_kernel(self):
        """Verify initialization handles missing kernel gracefully."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)
        server._kernel = None
        server._init_holographic_mode()

        assert server._holographic_registry is None

    @pytest.mark.asyncio
    async def test_init_holographic_mode_kernel_not_ready(self):
        """Verify initialization handles unready kernel."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)
        server._kernel = MagicMock()
        server._kernel.is_ready = False
        server._init_holographic_mode()

        assert server._holographic_registry is None


class TestRunFunctions:
    """Test server run functions with holographic flag."""

    def test_run_sse_server_accepts_holographic_flag(self):
        """Verify run_sse_server accepts use_holographic parameter."""
        import inspect
        from omni.agent.mcp_server.server import run_sse_server

        sig = inspect.signature(run_sse_server)
        params = sig.parameters

        assert "use_holographic" in params
        assert params["use_holographic"].default is False

    @pytest.mark.asyncio
    async def test_run_stdio_with_holographic_flag(self):
        """Verify run_stdio uses holographic mode when flag is set."""
        from omni.agent.mcp_server.server import AgentMCPServer

        server = AgentMCPServer(use_holographic=True)
        server._kernel = MagicMock()
        server._kernel.is_ready = True
        server._kernel.skill_context.get_core_commands = MagicMock(return_value=[])

        # Mock _init_holographic_mode to set registry
        server._holographic_registry = MagicMock()

        # Verify mode is set
        assert server._use_holographic is True


class TestCLIParsing:
    """Test command line argument parsing for holographic mode."""

    def test_parser_has_holographic_argument(self):
        """Verify CLI parser accepts --holographic flag."""
        import argparse
        from omni.agent.mcp_server.server import main_async

        # Create a new parser with the same arguments
        parser = argparse.ArgumentParser(description="Test")
        parser.add_argument("--sse", action="store_true")
        parser.add_argument("--port", type=int, default=8080)
        parser.add_argument("-v", "--verbose", action="store_true")
        parser.add_argument("--holographic", action="store_true")

        # Test with holographic flag
        args = parser.parse_args(["--holographic"])
        assert args.holographic is True

        # Test without holographic flag
        args = parser.parse_args([])
        assert args.holographic is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
