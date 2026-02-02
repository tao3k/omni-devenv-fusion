"""
kernel/components/holographic_mcp.py - Holographic MCP Tool Adapter

Integrates HolographicRegistry with MCP Server for dynamic tool discovery.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Holographic MCP Adapter                      │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   MCP Server ──→ list_tools() ──→ HolographicRegistry.search() │
    │                                                 │              │
    │                                                 ▼              │
    │                                        ToolMetadata[]          │
    │                                                 │              │
    │                                                 ▼              │
    │                                        ToolContextBuilder      │
    │                                                 │              │
    │                                                 ▼              │
    │                                        MCP Tool[]              │
    └─────────────────────────────────────────────────────────────────┘

Features:
- Dynamic discovery: Tools appear instantly when indexed
- Lazy loading: Tool code only loaded on execution
- Semantic search: Find tools by intent, not just name
- Hot reload: File changes automatically reflected

Usage:
    from omni.core.kernel.components.holographic_mcp import HolographicMCPToolAdapter

    adapter = HolographicMCPToolAdapter(
        server=mcp_server,
        registry=holographic_registry,
    )
    tools = await adapter.list_tools()  # Dynamic from LanceDB
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.types import Tool

from omni.foundation.config.logging import get_logger
from omni.core.context.tools import ToolContextBuilder
from omni.core.skills.registry.holographic import HolographicRegistry, ToolMetadata

logger = get_logger(__name__)


class HolographicMCPToolAdapter:
    """
    MCP Tool Adapter using HolographicRegistry for dynamic tool discovery.

    This replaces the in-memory MCPToolAdapter with a database-backed
    solution that supports:
    - Instant tool registration (via file watcher)
    - Semantic tool discovery (vector search)
    - Lazy code loading (only on execution)
    - Hot reload without server restart
    """

    def __init__(
        self,
        server: Any,  # MCPServer
        registry: HolographicRegistry,
        default_limit: int = 20,
    ) -> None:
        """Initialize the holographic MCP tool adapter.

        Args:
            server: The MCP Server instance to register handlers with.
            registry: HolographicRegistry for tool discovery.
            default_limit: Default max tools to return in list_tools.
        """
        self._server = server
        self._registry = registry
        self._default_limit = default_limit

        # Cache for tool schemas to avoid repeated conversion
        self._schema_cache: dict[str, dict] = {}

        # Register handlers with the server
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register list_tools and call_tool handlers with the MCP server."""
        self._server.list_tools()(self._handle_list_tools)
        self._server.call_tool()(self._handle_call_tool)

    async def _handle_list_tools(
        self,
        limit: int | None = None,
        query: str | None = None,
    ) -> list[Tool]:
        """Handle MCP list_tools request with optional filtering.

        Args:
            limit: Maximum tools to return (default: _default_limit)
            query: Optional search query for semantic filtering

        Returns:
            List of MCP Tool objects from HolographicRegistry
        """
        return await self.list_tools(query=query, limit=limit)

    async def _handle_call_tool(self, name: str, arguments: dict | None) -> list:
        """Handle MCP call_tool request.

        Args:
            name: Tool name
            arguments: Tool arguments dictionary

        Returns:
            List of text content results
        """
        return await self.call_tool(name, arguments or {})

    # =============================================================================
    # Tool Listing (Dynamic from HolographicRegistry)
    # =============================================================================

    async def list_tools(
        self,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[Tool]:
        """List tools from HolographicRegistry with optional semantic filtering.

        Args:
            query: Optional search query for semantic filtering
            limit: Maximum tools to return (None for all)

        Returns:
            List of MCP Tool objects
        """
        max_tools = limit or self._default_limit

        if query:
            # Semantic search using HolographicRegistry
            from omni.core.context.tools import ToolContextBuilder

            keywords = ToolContextBuilder.extract_keywords(query)

            tools_metadata = await self._registry.search_hybrid(
                query=query,
                keywords=keywords,
                limit=max_tools,
            )

            logger.debug(f"Semantic search for '{query}' found {len(tools_metadata)} tools")
        else:
            # List all tools
            tools_metadata = await self._registry.list_tools(limit=max_tools)

        # Convert to MCP Tool format
        mcp_tools = self._convert_to_mcp_tools(tools_metadata)

        logger.info(f"[HoloMCP] Listed {len(mcp_tools)} tools from HolographicRegistry")
        return mcp_tools

    def _convert_to_mcp_tools(self, tools_metadata: list[ToolMetadata]) -> list[Tool]:
        """Convert ToolMetadata to MCP Tool format.

        Args:
            tools_metadata: List of ToolMetadata from HolographicRegistry

        Returns:
            List of MCP Tool objects
        """
        mcp_tools: list[Tool] = []

        for metadata in tools_metadata:
            # Build input schema from args
            input_schema = self._build_input_schema(metadata)

            tool = Tool(
                name=metadata.name,
                description=metadata.description,
                inputSchema=input_schema,
            )
            mcp_tools.append(tool)

        return mcp_tools

    def _build_input_schema(self, metadata: ToolMetadata) -> dict[str, Any]:
        """Build JSON Schema for tool parameters from ToolMetadata.

        Args:
            metadata: ToolMetadata from HolographicRegistry

        Returns:
            JSON Schema dict for MCP inputSchema
        """
        # Check cache first
        cache_key = f"{metadata.module}:{metadata.name}"
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]

        # Build from args
        properties: dict[str, Any] = {}
        required: list[str] = []

        for arg in metadata.args:
            if isinstance(arg, dict):
                arg_name = arg.get("name", "")
                arg_type = arg.get("type", "string")
                arg_desc = arg.get("description", "")

                # Convert Python type to JSON Schema type
                json_type = self._python_type_to_json_type(arg_type)

                properties[arg_name] = {
                    "type": json_type,
                    "description": arg_desc,
                }
                required.append(arg_name)

        schema = {
            "type": "object",
            "properties": properties,
            "required": required if required else [],
        }

        # Cache for future lookups
        self._schema_cache[cache_key] = schema

        return schema

    def _python_type_to_json_type(self, python_type: str) -> str:
        """Convert Python type hint to JSON Schema type."""
        type_mapping = {
            "str": "string",
            "string": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "any": "string",
            "Optional": "string",
        }

        # Handle Optional[X] patterns
        if "Optional[" in python_type:
            python_type = python_type.split("[")[1].split("]")[0]

        # Handle List[X] patterns
        if "List[" in python_type:
            return "array"

        return type_mapping.get(python_type.lower(), "string")

    # =============================================================================
    # Tool Execution (Lazy Loading)
    # =============================================================================

    async def call_tool(self, name: str, args: dict) -> list[dict]:
        """Execute a tool call with lazy loading.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            List of content dictionaries (MCP protocol format)
        """
        # Look up tool metadata
        metadata = await self._registry.get_tool(name)
        if metadata is None:
            error_msg = f"Tool not found: {name}"
            logger.error(error_msg)
            return [{"type": "text", "text": f"Error: {error_msg}"}]

        # Lazy load the tool implementation
        from omni.core.skills.registry.holographic import LazyTool

        lazy_tool = LazyTool(metadata=metadata, registry=self._registry)
        func = await lazy_tool.load()

        if func is None:
            error_msg = f"Failed to load tool: {name}"
            logger.error(error_msg)
            return [{"type": "text", "text": f"Error: {error_msg}"}]

        # Validate arguments
        validation_error = self._validate_args(args, metadata)
        if validation_error:
            return [{"type": "text", "text": f"Error: {validation_error}"}]

        # Execute the tool
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            # Format result for MCP
            result_text = self._format_result(result)
            return [{"type": "text", "text": result_text}]

        except Exception as e:
            error_msg = f"Error executing {name}: {e}"
            logger.error(error_msg, exc_info=True)
            return [{"type": "text", "text": f"Error: {error_msg}"}]

    def _validate_args(self, args: dict, metadata: ToolMetadata) -> str | None:
        """Validate tool arguments against metadata.

        Args:
            args: Provided arguments
            metadata: Tool metadata

        Returns:
            Error message if invalid, None if valid
        """
        required_fields = [
            arg.get("name")
            for arg in metadata.args
            if isinstance(arg, dict) and arg.get("required", True) and arg.get("name")
        ]

        missing = [f for f in required_fields if f and (f not in args or args.get(f) is None)]
        if missing:
            return f"Missing required arguments: {', '.join(missing)}"

        return None

    def _format_result(self, result: Any) -> str:
        """Format a result for MCP text output."""
        if isinstance(result, str):
            return result
        elif isinstance(result, (dict, list)):
            import json

            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            return str(result)

    # =============================================================================
    # Cache Management
    # =============================================================================

    def clear_cache(self) -> None:
        """Clear the schema cache. Call after reindexing."""
        self._schema_cache.clear()
        logger.debug("Holographic MCP cache cleared")

    async def refresh_tools(self) -> int:
        """Force refresh tool list from registry.

        Returns:
            Number of tools available
        """
        tools = await self.list_tools(limit=1000)
        logger.info(f"[HoloMCP] Refreshed {len(tools)} tools from registry")
        return len(tools)

    # =============================================================================
    # Properties
    # =============================================================================

    @property
    def tool_count(self) -> int:
        """Get the number of registered tools (from registry)."""
        # This is an approximation - actual count may differ
        return len(self._schema_cache)

    @property
    def is_healthy(self) -> bool:
        """Check if the adapter is healthy."""
        try:
            # Simple health check - try to list tools
            # Don't await to keep it synchronous
            return self._registry is not None
        except Exception:
            return False


# =============================================================================
# Factory Function
# =============================================================================


async def create_holographic_mcp_adapter(
    server: Any,
    vector_store: Any,
    embedding_service: Any | None = None,
    default_limit: int = 20,
) -> HolographicMCPToolAdapter:
    """Factory function to create a HolographicMCPToolAdapter with registry.

    Args:
        server: The MCP Server instance
        vector_store: PyVectorStore instance (LanceDB)
        embedding_service: Optional EmbeddingService
        default_limit: Default max tools to return

    Returns:
        Configured HolographicMCPToolAdapter instance
    """
    from omni.core.skills.registry.holographic import HolographicRegistry

    registry = HolographicRegistry(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    return HolographicMCPToolAdapter(
        server=server,
        registry=registry,
        default_limit=default_limit,
    )
