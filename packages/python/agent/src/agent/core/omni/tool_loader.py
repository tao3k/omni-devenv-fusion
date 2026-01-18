"""
tool_loader.py - Tool Loading from Rust Scanner.

Loads tools from skills using Rust scanner (omni-core-rs):
- Discovers @skill_command decorated functions
- Creates JIT wrapper functions for execution
- Generates tool schemas for LLM consumption
- Manages tool aliases (e.g., "list_directory" -> "filesystem.list_directory")
"""

from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional

logger = structlog.get_logger(__name__)


class ToolLoader:
    """
    Tool Loader - Loads tools from Rust scanner and creates wrapper functions.

    Responsibilities:
    - Discover tools via omni_core_rs.scan_skill_tools
    - Create JIT wrapper functions for execution
    - Generate tool schemas for LLM
    - Manage tool aliases (e.g., "list_directory" -> "filesystem.list_directory")
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Any] = {}
        self._tool_aliases: Dict[str, str] = {}
        self._tool_schemas: List[Dict] = []
        self._loaded: bool = False

    def load_tools(self) -> None:
        """Load all available tools from skills."""
        if self._loaded:
            return

        logger.info("ToolLoader: Loading tools...")

        # Try to load tools from Rust scanner
        try:
            import omni_core_rs
            from agent.core.skill_runtime.support.jit_loader import (
                get_jit_loader,
                ToolRecord,
            )
            from common.skills_path import SKILLS_DIR

            # Check if scan_skill_tools is available
            if not hasattr(omni_core_rs, "scan_skill_tools"):
                raise AttributeError("scan_skill_tools not available in omni_core_rs")

            # Use SKILLS_DIR() to get the correct skills path from settings.yaml
            skills_path = str(SKILLS_DIR())
            rust_tools = omni_core_rs.scan_skill_tools(skills_path)

            if rust_tools:
                logger.info(
                    f"ToolLoader: Rust scanner discovered {len(rust_tools)} tools (JIT enabled)"
                )
                loader = get_jit_loader()

                # Group tools by tool_name for deduplication
                seen = set()

                for rt in rust_tools:
                    tool_name = rt.tool_name
                    if tool_name in seen:
                        continue
                    seen.add(tool_name)

                    # Create a wrapper function for JIT execution
                    record = ToolRecord.from_rust(rt)

                    def make_wrapper(rec: ToolRecord):
                        async def wrapper(**kwargs):
                            return await loader.execute_tool(rec, kwargs)

                        return wrapper

                    wrapper_func = make_wrapper(record)

                    # Store as a callable with metadata
                    self._tools[tool_name] = wrapper_func

                    # Create alias: "filesystem.list_directory" -> "list_directory"
                    if "." in tool_name:
                        alias = tool_name.split(".", 1)[1]  # Get the part after first dot
                        if alias not in self._tool_aliases:
                            self._tool_aliases[alias] = tool_name
                            logger.debug(f"ToolLoader: Created alias: {alias} -> {tool_name}")

                    logger.debug(f"ToolLoader: Loaded tool: {tool_name}")

                logger.info(
                    f"ToolLoader: Tool registry ready: {len(self._tools)} tools (JIT execution enabled)"
                )

        except (ImportError, AttributeError):
            logger.warning(
                "ToolLoader: omni_core_rs not available or scan_skill_tools missing, falling back to registry"
            )

            # Fallback: Load from skill registry (legacy)
            from agent.core.skill_registry import get_skill_tools

            skill_names = ["filesystem", "git", "testing", "memory"]
            for skill_name in skill_names:
                try:
                    tools = get_skill_tools(skill_name)
                    if tools:
                        self._tools.update(tools)
                        logger.debug(f"ToolLoader: Loaded {len(tools)} tools from {skill_name}")
                except Exception as e:
                    logger.debug(f"ToolLoader: Could not load tools from {skill_name}: {e}")

        # Generate tool schemas from JIT-loaded tools
        self._generate_schemas()
        self._loaded = True

    def _generate_schemas(self) -> None:
        """Generate tool schemas for LLM consumption."""
        from agent.core.skill_runtime.support.jit_loader import get_jit_loader

        loader = get_jit_loader()

        try:
            import omni_core_rs
            from common.skills_path import SKILLS_DIR
            from agent.core.skill_runtime.support.jit_loader import ToolRecord

            skills_path = str(SKILLS_DIR())
            all_rust_tools = omni_core_rs.scan_skill_tools(skills_path)

            for rt in all_rust_tools:
                if rt.tool_name in self._tools:
                    record = ToolRecord.from_rust(rt)
                    schema = loader.get_tool_schema(record)
                    self._tool_schemas.append(schema)

            logger.info(
                f"ToolLoader: Generated {len(self._tool_schemas)} tool schemas from Rust scanner"
            )

        except Exception as e:
            logger.warning(f"ToolLoader: Failed to generate tool schemas: {e}")
            self._tool_schemas = []

    @property
    def tools(self) -> Dict[str, Any]:
        """Get all loaded tools."""
        if not self._loaded:
            self.load_tools()
        return self._tools

    @property
    def aliases(self) -> Dict[str, str]:
        """Get tool aliases."""
        if not self._loaded:
            self.load_tools()
        return self._tool_aliases

    @property
    def schemas(self) -> List[Dict]:
        """Get tool schemas for LLM."""
        if not self._loaded:
            self.load_tools()
        return self._tool_schemas

    def get_tool(self, name: str) -> Optional[Any]:
        """Get a tool by name, checking aliases."""
        if not self._loaded:
            self.load_tools()

        resolved_name = name
        if name not in self._tools and name in self._tool_aliases:
            resolved_name = self._tool_aliases[name]
            logger.debug(f"ToolLoader: Resolved alias: {name} -> {resolved_name}")

        return self._tools.get(resolved_name)

    def get_schema(self, name: str) -> Optional[Dict]:
        """Get a tool schema by name."""
        if not self._loaded:
            self.load_tools()
        return self._tools.get(name)

    async def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """
        Execute a tool call.

        Args:
            tool_call: Dict with 'name' and 'input' keys

        Returns:
            Tool execution result string
        """
        tool_name = tool_call.get("name", "unknown")
        tool_input = tool_call.get("input", {})

        logger.info(
            "ToolLoader: Executing tool",
            tool=tool_name,
            input_preview=str(tool_input)[:100],
        )

        # Find and execute the tool
        tool_fn = self.get_tool(tool_name)
        if tool_fn is None:
            warning_msg = f"Unknown tool: {tool_name}"
            logger.warning("ToolLoader: Unknown tool", tool=tool_name)
            return f"Warning: {warning_msg}. Available tools: {list(self._tools.keys())}"

        try:
            result = tool_fn(**tool_input)

            # Handle async results FIRST before string conversion
            import asyncio

            if asyncio.iscoroutine(result):
                result = await result

            result_str = str(result) if result is not None else ""

            logger.info(
                "ToolLoader: Tool completed",
                tool=tool_name,
                result_preview=result_str[:100],
            )
            return result_str

        except Exception as e:
            error_msg = f"Tool '{tool_name}' failed: {str(e)}"
            logger.error(
                "ToolLoader: Tool failed",
                tool=tool_name,
                error=str(e),
            )
            return f"Error: {error_msg}"


# Convenience function for singleton access
_tool_loader: Optional[ToolLoader] = None


def get_tool_loader() -> ToolLoader:
    """Get the singleton ToolLoader instance."""
    global _tool_loader
    if _tool_loader is None:
        _tool_loader = ToolLoader()
    return _tool_loader


__all__ = ["ToolLoader", "get_tool_loader"]
