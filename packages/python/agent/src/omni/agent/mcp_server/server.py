"""
omni.agent.mcp_server.server - High-Performance MCP Gateway (v2.0)

Trinity Architecture - Agent Layer

High-Speed Interface exposing Rust-powered capabilities:
- Tools: Zero-copy via Rust Registry with Alias Mapping (Step 3)
- Resources: Context (Sniffer) + Memory (Checkpoint) (Steps 5-6)
- Prompts: Standardized system prompts

Key Features:
- Bi-directional alias mapping (LLM-friendly names -> canonical names)
- Glob pattern filtering for tool exposure
- Zero-copy Rust registry access
- [v2.1] Holographic Mode: Dynamic tool discovery via HolographicRegistry (Stage 3.5)

Usage:
    python -m omni.agent.mcp_server.server
    python -m omni.agent.mcp_server.server --sse --port 8080
    python -m omni.agent.mcp_server.server --holographic  # Enable holographic mode
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent, GetPromptResult, PromptMessage
from pydantic.networks import AnyUrl

from omni.foundation.config.logging import configure_logging, get_logger
from omni.core.kernel import get_kernel
from omni.core.config.loader import load_command_overrides, is_filtered
from omni.core.omni_tool import get_omni_tool_info
from omni.core.skills.runtime.omni_cell import ActionType, get_runner

# [NEW] Holographic Registry for dynamic tool discovery (Stage 3.5)
from omni.core.skills.registry.holographic import HolographicRegistry, ToolMetadata

# [NEW] Import shared formatting logic
from omni.foundation.utils.formatting import sanitize_tool_args, one_line_preview
from omni.mcp.transport.sse import SSEServer
from omni.mcp.transport.stdio import stdio_server

# Configure logging
configure_logging(level="INFO")
logger = get_logger("omni.agent.mcp_server")


class AgentMCPServer:
    """
    High-Performance MCP Server (v2.1)

    Leverages Rust components for microsecond-level responses:
    - tools/list: Zero-copy via Rust Vector Store registry
    - resources/read: Direct from Sniffer (context) and Checkpoint Store (memory)

    Features:
    - Bi-directional alias mapping: LLM sees 'save_memory', kernel executes 'memory.remember_insight'
    - Glob pattern filtering: Control which tools are exposed to LLM
    - [v2.1] Holographic Mode: Dynamic tool discovery via HolographicRegistry (Stage 3.5)
    """

    def __init__(self, use_holographic: bool = False):
        """Initialize the MCP Server.

        Args:
            use_holographic: If True, use HolographicRegistry for dynamic tool discovery.
                           If False, use traditional kernel-based tool listing.
        """
        self._kernel = None
        self._app = Server("omni-agent-os-v2")
        self._start_time = time.time()

        # [v2.1] Holographic Mode flag
        self._use_holographic = use_holographic
        self._holographic_adapter = None
        self._holographic_registry: HolographicRegistry | None = None

        # [NEW] Routing Tables for Alias Resolution
        self._alias_to_real: dict[str, str] = {}  # alias -> real_name (Incoming calls)
        self._real_to_display: dict[str, dict] = {}  # real_name -> {name, append_doc} (Outgoing)

        self._build_routing_table()
        self._register_handlers()

    def _init_holographic_mode(self) -> None:
        """Initialize Holographic Registry and Adapter for dynamic tool discovery."""
        if not self._use_holographic:
            return

        if not self._kernel or not self._kernel.is_ready:
            logger.warning("Kernel not ready, cannot initialize holographic mode")
            return

        try:
            # Get the router's semantic indexer to access its registry
            router = getattr(self._kernel, "router", None)
            if router and hasattr(router, "_semantic"):
                semantic = router._semantic
                if hasattr(semantic, "_indexer"):
                    indexer = semantic._indexer
                    if hasattr(indexer, "_registry"):
                        self._holographic_registry = indexer._registry
                        logger.info("✅ Holographic Registry initialized from router's indexer")
                        return

            # Fallback: Check if kernel has direct registry access
            if hasattr(self._kernel, "skill_context"):
                # Use the skill context to get tools and create registry on demand
                commands = self._kernel.skill_context.get_core_commands()
                logger.info(f"Found {len(commands)} commands for holographic registry")

            logger.info(
                "ℹ️  Holographic mode enabled but no registry found - using adapter initialization"
            )

        except Exception as e:
            logger.error(f"Failed to initialize holographic mode: {e}")

    # =============================================================================
    # [v2.1] Holographic Tool Discovery Methods (Stage 3.5)
    # =============================================================================

    async def _list_holographic_tools(
        self,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[Tool]:
        """List tools from HolographicRegistry with optional semantic filtering.

        Args:
            query: Optional search query for semantic filtering
            limit: Maximum tools to return

        Returns:
            List of MCP Tool objects from HolographicRegistry
        """
        if not self._holographic_registry:
            logger.warning("Holographic registry not available")
            return []

        max_tools = limit or 20

        try:
            if query:
                # Semantic search using HolographicRegistry
                from omni.core.context.tools import ToolContextBuilder

                keywords = ToolContextBuilder.extract_keywords(query)
                tools_metadata = await self._holographic_registry.search_hybrid(
                    query=query,
                    keywords=keywords,
                    limit=max_tools,
                )
                logger.debug(f"Semantic search for '{query}' found {len(tools_metadata)} tools")
            else:
                # List all tools
                tools_metadata = await self._holographic_registry.list_tools(limit=max_tools)

            # Convert to MCP Tool format
            mcp_tools = self._convert_holographic_to_mcp_tools(tools_metadata)
            logger.info(f"[HoloMCP] Listed {len(mcp_tools)} tools from HolographicRegistry")
            return mcp_tools

        except Exception as e:
            logger.error(f"Failed to list holographic tools: {e}")
            return []

    def _convert_holographic_to_mcp_tools(self, tools_metadata: list[ToolMetadata]) -> list[Tool]:
        """Convert ToolMetadata to MCP Tool format.

        Args:
            tools_metadata: List of ToolMetadata from HolographicRegistry

        Returns:
            List of MCP Tool objects
        """
        mcp_tools: list[Tool] = []

        for metadata in tools_metadata:
            # Build input schema from args
            input_schema = self._build_holographic_input_schema(metadata)

            tool = Tool(
                name=metadata.name,
                description=metadata.description,
                inputSchema=input_schema,
            )
            mcp_tools.append(tool)

        return mcp_tools

    def _build_holographic_input_schema(self, metadata: ToolMetadata) -> dict[str, Any]:
        """Build JSON Schema for tool parameters from ToolMetadata.

        Args:
            metadata: ToolMetadata from HolographicRegistry

        Returns:
            JSON Schema dict for MCP inputSchema
        """
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

        return {
            "type": "object",
            "properties": properties,
            "required": required if required else [],
        }

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

    async def _call_holographic_tool(self, name: str, args: dict) -> list[TextContent]:
        """Execute a holographic tool with lazy loading.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            List of text content results
        """
        if not self._holographic_registry:
            return [TextContent(type="text", text="Error: Holographic registry not available")]

        # Look up tool metadata
        metadata = await self._holographic_registry.get_tool(name)
        if metadata is None:
            return [TextContent(type="text", text=f"Tool not found: {name}")]

        # Lazy load the tool implementation
        from omni.core.skills.registry.holographic import LazyTool

        lazy_tool = LazyTool(metadata=metadata, registry=self._holographic_registry)
        func = await lazy_tool.load()

        if func is None:
            return [TextContent(type="text", text=f"Failed to load tool: {name}")]

        # Execute the tool
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            return [TextContent(type="text", text=str(result))]

        except Exception as e:
            logger.error(f"Error executing {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    def _build_routing_table(self):
        """Pre-compute routing tables from overrides config."""
        overrides = load_command_overrides()

        for real_name, config in overrides.commands.items():
            if config.alias:
                # Map 'save_memory' -> 'memory.remember_insight' (for incoming calls)
                self._alias_to_real[config.alias] = real_name

                # Store display metadata (for outgoing list_tools)
                self._real_to_display[real_name] = {
                    "name": config.alias,
                    "append_doc": config.append_doc,
                }

        if self._alias_to_real:
            logger.info(f"🔀 Built routing table with {len(self._alias_to_real)} aliases")

    def _validate_overrides(self):
        """Check if configured overrides actually exist in kernel.

        Logs warnings if settings.yaml contains overrides for tools that don't exist.
        """
        if not self._kernel or not self._kernel.is_ready:
            return

        # Get all real commands
        real_commands = set(self._kernel.skill_context.get_core_commands())
        overrides = load_command_overrides()

        for configured_name in overrides.commands.keys():
            if configured_name not in real_commands:
                # Find close matches or just list a few
                suggestions = sorted(
                    [cmd for cmd in real_commands if cmd.startswith(configured_name.split(".")[0])]
                )
                hint = f" Did you mean: {', '.join(suggestions[:3])}?" if suggestions else ""

                logger.warning(
                    f"⚠️  Config Warning: Override key '{configured_name}' does not match any loaded tool.{hint}"
                )

    def _register_handlers(self):
        """Register MCP protocol handlers."""

        @self._app.list_tools()
        async def list_tools(limit: int | None = None, query: str | None = None) -> list[Tool]:
            """
            List tools using Zero-Copy Rust Registry with Alias Resolution.

            Features:
            - [v2.1] Holographic Mode: Dynamic discovery via HolographicRegistry
            - Applies command overrides (alias, append_doc)
            - Filters out commands via glob patterns
            - Performance: ~1-5ms (vs ~100ms+ for Python iteration)
            """
            # [v2.1] Holographic Mode: Use dynamic tool discovery
            if self._use_holographic and self._holographic_registry:
                return await self._list_holographic_tools(query=query, limit=limit)

            if not self._kernel or not self._kernel.is_ready:
                logger.warning("Kernel not ready, returning empty tools list")
                return []

            try:
                # Direct access to skill context - no iteration overhead
                context = self._kernel.skill_context
                commands = context.get_core_commands()

                mcp_tools = []

                # [MASTER] Omni - Highest Authority Universal Gateway (from common module)
                omni_info = get_omni_tool_info()
                mcp_tools.append(
                    Tool(
                        name="omni",
                        description=omni_info["description"],
                        inputSchema=omni_info["inputSchema"],
                    )
                )

                # [NEW] OmniCell Kernel Tools - Direct Rust/Nushell Bridge
                # These tools bypass skill resolution for maximum performance
                mcp_tools.append(
                    Tool(
                        name="sys_query",
                        description="[READ-ONLY] Execute a system query via OmniCell. Returns structured JSON data for file listing, reading, and searching.",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Nushell command to execute (read-only: ls, cat, grep, etc.)",
                                }
                            },
                            "required": ["query"],
                        },
                    )
                )

                mcp_tools.append(
                    Tool(
                        name="sys_exec",
                        description="[WRITE/ACTION] Execute a system command via OmniCell. Use for mutations: save, rm, mv, cp, mkdir. All mutations are safety-validated.",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "script": {
                                    "type": "string",
                                    "description": "Nushell command to execute (mutations: save, rm, mv, cp, etc.)",
                                }
                            },
                            "required": ["script"],
                        },
                    )
                )

                for cmd_name in commands:
                    # [NEW] 1. Apply Filter (Global Hide)
                    if is_filtered(cmd_name):
                        continue

                    cmd = context.get_command(cmd_name)
                    if cmd is None:
                        continue

                    # [NEW] 2. Apply Alias / Renaming Logic
                    override = self._real_to_display.get(cmd_name, {})
                    exposed_name = override.get("name", cmd_name)

                    # Build exposed description
                    base_desc = getattr(cmd, "description", "") or f"Execute {cmd_name}"
                    extra_doc = override.get("append_doc")
                    exposed_desc = f"{base_desc} {extra_doc}" if extra_doc else base_desc

                    # Fast path: Use cached schema from Rust
                    input_schema = getattr(cmd, "input_schema", {})

                    mcp_tools.append(
                        Tool(
                            name=exposed_name,  # LLM sees 'save_memory'
                            description=exposed_desc,
                            inputSchema=input_schema,
                        )
                    )

                elapsed = time.time() - self._start_time
                logger.info(
                    f"⚡ Served {len(mcp_tools)} tools via Rust Registry (uptime: {elapsed:.2f}s)"
                )
                return mcp_tools

            except Exception as e:
                logger.error(f"Failed to list tools: {e}")
                return []

        @self._app.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[Any]:
            """Execute tool via Kernel with Clean Logging.

            [v2.1] Holographic Mode: Supports lazy-loaded tools from HolographicRegistry.
            """
            # [v2.1] Holographic Mode: Use lazy-loaded tool execution
            if self._use_holographic and self._holographic_registry:
                return await self._call_holographic_tool(name, arguments)

            # [NEW] Universal Master Proxy Support
            if name == "omni":
                intent = arguments.get("intent")
                real_target = arguments.get("command")
                real_args = arguments.get("args", {})

                # [NEW] Intent-based Routing Logic
                if intent and not real_target:
                    logger.info(f"🔮 Master Proxy Routing Intent: '{intent}'")
                    if not self._kernel or not self._kernel.is_ready:
                        return [
                            TextContent(type="text", text="Error: Kernel not ready for routing")
                        ]

                    route_result = await self._kernel.router.route(intent)
                    if route_result and route_result.command_name:
                        real_target = f"{route_result.skill_name}.{route_result.command_name}"
                        logger.info(
                            f"🎯 Routed to: {real_target} (Score: {route_result.score:.2f})"
                        )
                    else:
                        return [
                            TextContent(
                                type="text",
                                text=f"Error: Could not resolve intent '{intent}' to any command",
                            )
                        ]

                if not real_target:
                    return [
                        TextContent(
                            type="text",
                            text="Error: Either 'command' or 'intent' is required for omni proxy",
                        )
                    ]

                name = real_target
                arguments = real_args

            if not self._kernel or not self._kernel.is_ready:
                return [TextContent(type="text", text="Error: Kernel not ready")]

            try:
                # [NEW] Log the INCOMING request cleanly
                # Solves the "noise" problem when Claude writes huge files
                clean_args = sanitize_tool_args(arguments)
                logger.info(f"🔧 Call: {name}({clean_args})")

                # Resolve Alias
                real_command = self._alias_to_real.get(name, name)

                # Optional: Debug log for alias resolution
                if name != real_command:
                    logger.debug(f"🔀 Route Alias: '{name}' -> '{real_command}'")

                # Execute
                start_t = time.time()
                result = await self._kernel.execute_tool(real_command, arguments, caller="mcp")
                duration = time.time() - start_t

                # [NEW] Log the OUTGOING result cleanly
                # Prevents "read_file" from flooding the terminal
                clean_result = one_line_preview(result, max_len=100)
                logger.info(f"✅ Done: {name} -> {clean_result} ({duration:.2f}s)")

                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                logger.error(f"❌ Fail: {name} -> {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @self._app.call_tool()
        async def system_status(arguments: dict) -> list[Any]:
            """Get system status for debugging startup issues.

            Returns kernel readiness, cortex status, and component health.
            [v2.1] Includes holographic mode status.
            """
            try:
                cortex_ready = False
                indexed_count = 0
                router_status = "unknown"
                holographic_status = "disabled"

                if self._kernel and self._kernel.is_ready:
                    # Check router and cortex status
                    router = getattr(self._kernel, "router", None)
                    if router:
                        semantic = getattr(router, "_semantic", None)
                        if semantic:
                            indexer = getattr(semantic, "_indexer", None)
                            if indexer:
                                cortex_ready = indexer.is_ready
                                stats = indexer.get_stats()
                                indexed_count = stats.get("entries_indexed", 0)

                    router_status = "ready" if router else "not_initialized"
                    skill_count = len(self._kernel.skill_context.get_core_commands())

                    # [v2.1] Check holographic status
                    if self._use_holographic:
                        if self._holographic_registry:
                            holographic_status = "active"
                        else:
                            holographic_status = "enabled (no registry)"
                    else:
                        holographic_status = "disabled"

                else:
                    skill_count = 0

                uptime = time.time() - self._start_time
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "kernel_ready": self._kernel.is_ready if self._kernel else False,
                                "cortex_ready": cortex_ready,
                                "cortex_indexed": indexed_count,
                                "router_status": router_status,
                                "tool_count": skill_count,
                                "holographic_mode": holographic_status,
                                "uptime_seconds": round(uptime, 2),
                                "version": "2.1.0",
                            },
                            indent=2,
                        ),
                    )
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @self._app.call_tool()
        async def sys_query(arguments: dict) -> list[Any]:
            """[READ-ONLY] Execute a system query via OmniCell to find files or read data.

            Use this for read-only operations:
            - List files (ls, find)
            - Read file contents (open, cat)
            - Search for patterns (grep, where)
            - Get system information (ps, date, git status)

            Returns structured JSON data for easy parsing.
            """
            try:
                query = arguments.get("query")
                if not query:
                    return [TextContent(type="text", text="Error: 'query' parameter required")]

                logger.info(f"[MCP] sys_query called: {query[:100]}...")
                runner = get_runner()
                result = await runner.run(query, action=ActionType.OBSERVE, ensure_structured=True)

                if result.status == "success":
                    data_preview = (
                        str(result.data)[:200] + "..."
                        if len(str(result.data)) > 200
                        else str(result.data)
                    )
                    logger.info(f"[MCP] sys_query success: {data_preview}")
                    return [TextContent(type="text", text=json.dumps(result.data, indent=2))]
                else:
                    error_msg = result.metadata.get(
                        "reason", result.metadata.get("error_msg", "unknown")
                    )
                    logger.error(f"[MCP] sys_query error: {error_msg}")
                    return [
                        TextContent(
                            type="text",
                            text=f"Error: {result.status} - {error_msg}",
                        )
                    ]
            except Exception as e:
                logger.error(f"sys_query failed: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @self._app.call_tool()
        async def sys_exec(arguments: dict) -> list[Any]:
            """[WRITE/ACTION] Execute a system command via OmniCell that modifies files.

            Use this for mutation operations:
            - Create/update files (save, write, echo)
            - Move or copy files (mv, cp)
            - Delete files (rm)
            - Create directories (mkdir)
            - Modify permissions (chmod)

            All mutations are validated for safety before execution.
            """
            try:
                script = arguments.get("script")
                if not script:
                    return [TextContent(type="text", text="Error: 'script' parameter required")]

                logger.info(f"[MCP] sys_exec called: {script[:100]}...")
                runner = get_runner()
                result = await runner.run(script, action=ActionType.MUTATE, ensure_structured=False)

                if result.status == "success":
                    # For mutations, return a concise success message
                    output = (
                        result.data if isinstance(result.data, str) else json.dumps(result.data)
                    )
                    logger.info(f"[MCP] sys_exec success: {output}")
                    return [TextContent(type="text", text=f"Success: {output}")]
                elif result.status == "blocked":
                    reason = result.metadata.get("reason", "Safety check failed")
                    logger.warn(f"[MCP] sys_exec blocked: {reason}")
                    return [
                        TextContent(
                            type="text",
                            text=f"Blocked: {reason}",
                        )
                    ]
                else:
                    error_msg = result.metadata.get("error_msg", result.status)
                    logger.error(f"[MCP] sys_exec error: {error_msg}")
                    return [
                        TextContent(
                            type="text",
                            text=f"Error: {error_msg}",
                        )
                    ]
            except Exception as e:
                logger.error(f"sys_exec failed: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        @self._app.list_resources()
        async def list_resources() -> list[Resource]:
            """Expose Agentic OS internals as Resources."""
            return [
                Resource(
                    uri=AnyUrl("omni://project/context"),
                    name="Project Context (Sniffer)",
                    description="Active frameworks and languages detected by Rust Sniffer",
                    mimeType="application/json",
                ),
                Resource(
                    uri=AnyUrl("omni://memory/latest"),
                    name="Agent Short-term Memory",
                    description="Latest snapshot of agent state from LanceDB",
                    mimeType="application/json",
                ),
                Resource(
                    uri=AnyUrl("omni://system/stats"),
                    name="System Statistics",
                    description="Runtime statistics (uptime, memory, tool counts)",
                    mimeType="application/json",
                ),
            ]

        @self._app.read_resource()
        async def read_resource(uri: AnyUrl) -> str:
            """Read resource data from Rust components."""
            if not self._kernel or not self._kernel.is_ready:
                return json.dumps({"error": "Kernel not ready"})

            uri_str = str(uri)

            if uri_str == "omni://project/context":
                return self._read_project_context()

            elif uri_str == "omni://memory/latest":
                return await self._read_agent_memory()

            elif uri_str == "omni://system/stats":
                return self._read_system_stats()

            raise ValueError(f"Resource not found: {uri}")

        @self._app.list_prompts()
        async def list_prompts() -> list[Any]:
            """List available prompts."""
            return [
                {"name": "default", "description": "Standard Omni Agent system prompt"},
                {"name": "researcher", "description": "Research-focused agent prompt"},
                {"name": "developer", "description": "Code-focused agent prompt"},
            ]

        @self._app.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
            """Get prompt content."""
            prompts = {
                "default": self._get_default_prompt(),
                "researcher": self._get_researcher_prompt(),
                "developer": self._get_developer_prompt(),
            }

            if name not in prompts:
                raise ValueError(f"Prompt not found: {name}")

            return GetPromptResult(
                description=prompts[name]["description"],
                messages=[
                    PromptMessage(
                        role="user", content=TextContent(type="text", text=prompts[name]["content"])
                    )
                ],
            )

    def _read_project_context(self) -> str:
        """Read project context from Sniffer (Step 5 integration)."""
        try:
            sniffer = getattr(self._kernel, "router", None)
            if sniffer and hasattr(sniffer, "sniffer"):
                sniffer_instance = sniffer.sniffer
                if hasattr(sniffer_instance, "_active_contexts"):
                    contexts = list(sniffer_instance._active_contexts)
                else:
                    contexts = sniffer_instance.sniff(".") or []
            else:
                contexts = []

            return json.dumps(
                {
                    "contexts": contexts,
                    "timestamp": time.time(),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    async def _read_agent_memory(self) -> str:
        """Read latest agent state from Checkpoint Store (Step 6 integration)."""
        try:
            # Guard against None kernel
            if not self._kernel or not self._kernel.is_ready:
                return json.dumps({"error": "Kernel not ready"}, indent=2)

            # Use configured path from settings.yaml
            from omni.foundation.config.dirs import get_checkpoints_db_path
            from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

            db_path = get_checkpoints_db_path()
            checkpointer = RustLanceCheckpointSaver(
                base_path=str(db_path),
                table_name="agent_checkpoints",
                notify_on_save=False,
            )

            config = {"configurable": {"thread_id": "mcp_session"}}
            tuple_data = checkpointer.get_tuple(config)

            if tuple_data:
                return json.dumps(
                    {
                        "checkpoint": tuple_data.checkpoint,
                        "metadata": tuple_data.metadata,
                        "timestamp": time.time(),
                    },
                    indent=2,
                    default=str,
                )

            return json.dumps({"status": "empty", "timestamp": time.time()}, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    def _read_system_stats(self) -> str:
        """Read system statistics."""
        try:
            uptime = time.time() - self._start_time

            # Get tool count
            tool_count = 0
            if self._kernel and self._kernel.is_ready:
                tool_count = len(self._kernel.skill_context.get_core_commands())

            return json.dumps(
                {
                    "uptime_seconds": round(uptime, 2),
                    "tool_count": tool_count,
                    "kernel_ready": self._kernel.is_ready if self._kernel else False,
                    "version": "2.0.0",
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    def _get_default_prompt(self) -> dict:
        """Get default system prompt."""
        return {
            "description": "Standard Omni Agent system prompt",
            "content": """You are Omni-Dev Fusion, an advanced AI programming assistant.

Core Principles:
1. Use high-level skills (researcher, code_tools, git_smart) first
2. Use skill.discover when you need to find new capabilities
3. Stop immediately if you are stuck in a loop
4. Output 'EXIT_LOOP_NOW' only when the user's intent is fully satisfied

You have access to:
- File system operations (read, write, list, delete)
- Git operations (status, commit, log, branch)
- Research capabilities (web search, code analysis)
- Code execution and refactoring

Always explain your reasoning before taking action.""",
        }

    def _get_researcher_prompt(self) -> dict:
        """Get researcher-focused prompt."""
        return {
            "description": "Research-focused agent prompt",
            "content": """You are Omni-Researcher, an AI assistant specialized in code analysis and research.

Your approach:
1. First understand the codebase structure using researcher skills
2. Use structural code analysis to find relevant code
3. Document your findings clearly
4. Provide actionable insights

Focus on:
- Code architecture understanding
- Dependency analysis
- Pattern discovery
- Documentation generation""",
        }

    def _get_developer_prompt(self) -> dict:
        """Get developer-focused prompt."""
        return {
            "description": "Code-focused agent prompt",
            "content": """You are Omni-Developer, an AI assistant specialized in code modification and debugging.

Your approach:
1. Understand the task and existing code structure
2. Make minimal, focused changes
3. Write tests for your changes
4. Verify changes don't break existing functionality

Focus on:
- Implementing features correctly
- Writing clean, maintainable code
- Adding appropriate error handling
- Testing thoroughly""",
        }

    async def run_stdio(self, verbose: bool = False) -> None:
        """Run the MCP server over Stdio."""
        mode = "Holographic" if self._use_holographic else "Standard"
        logger.info(f"🚀 Starting Agent MCP Server v2.1 ({mode} Mode - STDIO)")

        # Initialize kernel
        self._kernel = get_kernel()
        if not self._kernel.is_ready:
            await self._kernel.initialize()

            # [FIX] Register MCP server BEFORE kernel.start() to ensure Live-Wire
            # callbacks can access _mcp_server when file changes are detected
            from .lifespan import set_mcp_server

            set_mcp_server(self._app)
            logger.debug("MCP server registered for Live-Wire notifications")

            await self._kernel.start()
            logger.info(
                f"✅ Kernel ready with {len(self._kernel.skill_context.get_core_commands())} tools"
            )

        # [v2.1] Initialize holographic mode after kernel is ready
        if self._use_holographic:
            self._init_holographic_mode()
            if self._holographic_registry:
                logger.info("🔮 Holographic mode active - tools will be dynamically discovered")
            else:
                logger.warning("⚠️  Holographic mode enabled but registry not available")

        # [NEW] Validate overrides against loaded tools
        self._validate_overrides()

        # Enable verbose mode (hot reload is already enabled by default)
        if verbose:
            logger.info("👀 Verbose mode enabled")

        try:
            # Use stdio_server context manager for proper stream handling
            async with stdio_server() as (read_stream, write_stream):
                await self._app.run(
                    read_stream,
                    write_stream,
                    self._app.create_initialization_options(),
                )
        except asyncio.CancelledError:
            logger.info("STDIO server cancelled")
        except KeyboardInterrupt:
            logger.info("STDIO server interrupted")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self._kernel:
                await self._kernel.shutdown()
                logger.info("🔒 Kernel shutdown complete")


async def run_stdio_server(verbose: bool = False) -> None:
    """Run the Agent in STDIO mode."""
    server = AgentMCPServer()
    await server.run_stdio(verbose=verbose)


async def run_sse_server(
    port: int = 8080, verbose: bool = False, use_holographic: bool = False
) -> None:
    """Run the Agent in SSE mode.

    Args:
        port: Port for SSE server (default: 8080)
        verbose: Enable verbose logging
        use_holographic: Enable holographic mode for dynamic tool discovery
    """
    mode = "Holographic" if use_holographic else "Standard"
    logger.info(f"🚀 Starting Agent MCP Server v2.1 ({mode} Mode - SSE on port {port})")

    server = AgentMCPServer(use_holographic=use_holographic)

    # Initialize kernel
    server._kernel = get_kernel()
    if not server._kernel.is_ready:
        await server._kernel.initialize()
        await server._kernel.start()
        logger.info(
            f"✅ Kernel ready with {len(server._kernel.skill_context.get_core_commands())} tools"
        )

    # [v2.1] Initialize holographic mode after kernel is ready
    if use_holographic:
        server._init_holographic_mode()
        if server._holographic_registry:
            logger.info("🔮 Holographic mode active - tools will be dynamically discovered")
        else:
            logger.warning("⚠️  Holographic mode enabled but registry not available")

    # [NEW] Validate overrides
    server._validate_overrides()

    # Create SSE server
    sse = SSEServer(server._app, host="0.0.0.0", port=port)

    init_options = {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True},
            "resources": {"subscribe": True},
            "prompts": {"listChanged": False},
        },
        "serverInfo": {"name": "omni-agent", "version": "2.1.0"},
    }

    try:
        await sse.run(init_options)
    except KeyboardInterrupt:
        logger.info("SSE server interrupted")
    finally:
        if server._kernel:
            await server._kernel.shutdown()


async def main_async() -> None:
    """Main async entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Omni Agent MCP Server v2.1")
    parser.add_argument("--sse", action="store_true", help="Run in SSE mode instead of STDIO")
    parser.add_argument("--port", type=int, default=8080, help="Port for SSE mode (default: 8080)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument(
        "--holographic",
        action="store_true",
        help="Enable holographic mode for dynamic tool discovery via HolographicRegistry",
    )

    args = parser.parse_args()

    try:
        if args.sse:
            await run_sse_server(
                port=args.port,
                verbose=args.verbose,
                use_holographic=args.holographic,
            )
        else:
            await run_stdio_server(verbose=args.verbose)
    except asyncio.CancelledError:
        logger.info("Server cancelled")


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")


if __name__ == "__main__":
    main()
