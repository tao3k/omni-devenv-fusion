"""
agent/core/adaptive_loader.py
Phase 68-69: Dynamic Context Injection - Adaptive Tool Loader
Phase 71: Memory Integration

Implements "Core + Dynamic" tool loading strategy:
- Core Tools: Always present (life support for Agent)
- Dynamic Tools: Loaded based on user intent (Hybrid Search)
- Memory: Relevant past experiences injected into context

Configuration is read from settings.yaml:
- adaptive.core_tools
- adaptive.dynamic_tools_limit
- adaptive.min_core_tools
- adaptive.rerank_threshold
- adaptive.schema_cache_ttl
- adaptive.auto_optimize
"""

import json
import time
from typing import Any

from common.config.settings import get_setting

# Lazy imports for memory (Phase 71)
_cached_memory_interceptor: Any = None

_cached_logger: Any = None


def _get_logger() -> Any:
    """Lazy logger initialization."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Schema Cache (Simple in-memory cache)
# =============================================================================

_schema_cache: dict[str, tuple[dict, float]] = {}


def _get_cached_schema(tool_name: str) -> dict[str, Any] | None:
    """Get cached schema if valid."""
    if tool_name in _schema_cache:
        schema, timestamp = _schema_cache[tool_name]
        if time.time() - timestamp < get_setting("adaptive.schema_cache_ttl", 300):
            return schema
        del _schema_cache[tool_name]
    return None


def _cache_schema(tool_name: str, schema: dict[str, Any]) -> None:
    """Cache a tool schema."""
    _schema_cache[tool_name] = (schema, time.time())


# =============================================================================
# Core Tools (from settings.yaml)
# =============================================================================


def get_core_tools() -> list[str]:
    """
    Get the list of core tools (always loaded).

    Loaded from settings.yaml: adaptive.core_tools
    """
    return get_setting(
        "adaptive.core_tools",
        [
            "skill.search_tools",
            "memory.add_note",
            "memory.search_memory",
            "task.update",
            "knowledge.get_development_context",
        ],
    )


def is_core_tool(tool_name: str) -> bool:
    """Check if a tool is a Core Tool."""
    return tool_name in get_core_tools()


def get_dynamic_tools_limit() -> int:
    """Get max dynamic tools per request."""
    return get_setting("adaptive.dynamic_tools_limit", 15)


# =============================================================================
# Core Tool Schema Provider
# =============================================================================


def get_core_tool_schemas() -> list[dict[str, Any]]:
    """
    Get schemas for all Core Tools.

    Returns list of tool schemas for tools that must always be available.
    """
    from agent.core.skill_manager.jit_loader import get_jit_loader
    from common.skills_path import SKILLS_DIR

    schemas = []
    jit = get_jit_loader()

    # Get all tools from Rust scanner
    try:
        import omni_core_rs

        skills_path = str(SKILLS_DIR())
        all_tools = omni_core_rs.scan_skill_tools(skills_path)
    except Exception as e:
        _get_logger().warning("Failed to scan skill tools", error=str(e))
        all_tools = []

    # Create a lookup dict by tool name
    tools_by_name = {t.tool_name: t for t in all_tools}

    for tool_name in get_core_tools():
        # Check cache first
        cached = _get_cached_schema(tool_name)
        if cached:
            schemas.append(cached)
            continue

        try:
            # Look up the tool by name
            rust_record = tools_by_name.get(tool_name)
            if rust_record:
                # Create ToolRecord from Rust record
                from agent.core.skill_manager.jit_loader import ToolRecord

                record = ToolRecord.from_rust(rust_record)
                schema = jit.get_tool_schema(record)
                if schema:
                    _cache_schema(tool_name, schema)
                    schemas.append(schema)
            else:
                _get_logger().warning("Core tool not found in scanner", tool=tool_name)
        except Exception:
            _get_logger().warning("Failed to get schema for core tool", tool=tool_name)

    return schemas


# =============================================================================
# Adaptive Loader
# =============================================================================


class AdaptiveLoader:
    """
    Phase 68: Adaptive Tool Loader.

    Implements "Core + Dynamic" loading strategy:
    1. Always includes Core Tools (life support)
    2. Loads Dynamic Tools based on intent (Hybrid Search)
    3. Merges and deduplicates
    4. Returns optimized tool list for LLM context
    """

    _instance: "AdaptiveLoader | None" = None

    def __new__(cls) -> "AdaptiveLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._jit_loader = None

    @property
    def jit_loader(self):
        """Lazy load JIT loader."""
        if self._jit_loader is None:
            from agent.core.skill_manager.jit_loader import get_jit_loader

            self._jit_loader = get_jit_loader()
        return self._jit_loader

    async def get_context_tools(
        self,
        user_query: str,
        dynamic_limit: int | None = None,
        include_core: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get optimized tool list for current context.

        Args:
            user_query: The user's input query for intent matching.
            dynamic_limit: Max dynamic tools to load (default: from settings.yaml).
            include_core: Whether to include Core Tools (default: True).

        Returns:
            List of tool schemas optimized for LLM context.
        """
        logger = _get_logger().bind(query=user_query[:50])
        result_schemas: list[dict[str, Any]] = []
        dynamic_limit = dynamic_limit or get_dynamic_tools_limit()

        # Step 1: Get Core Tools (always present)
        if include_core:
            core_schemas = get_core_tool_schemas()
            result_schemas.extend(core_schemas)
            logger.debug("core_tools_loaded", count=len(core_schemas))

        # Step 2: Hybrid Search for Dynamic Tools
        try:
            from agent.core.router import get_intent_router

            router = get_intent_router()
            search_results = await router.search_tools(user_query, limit=dynamic_limit)

            if search_results:
                # Convert search results to schemas
                dynamic_schemas = []
                seen_names = set(s.get("name", "") for s in result_schemas)

                for item in search_results:
                    tool_name = item.get("id", "")
                    if not tool_name or tool_name in seen_names:
                        continue

                    seen_names.add(tool_name)

                    # Build schema from search result
                    metadata = item.get("metadata", {}) or {}
                    input_schema_str = metadata.get("input_schema", "{}")
                    try:
                        input_schema = (
                            json.loads(input_schema_str)
                            if isinstance(input_schema_str, str)
                            else input_schema_str
                        )
                    except json.JSONDecodeError:
                        input_schema = {"type": "object", "properties": {}}

                    schema = {
                        "name": tool_name,
                        "description": item.get("content", ""),
                        "inputSchema": input_schema,
                    }

                    # Cache it
                    _cache_schema(tool_name, schema)
                    dynamic_schemas.append(schema)

                result_schemas.extend(dynamic_schemas)
                logger.debug(
                    "dynamic_tools_loaded",
                    count=len(dynamic_schemas),
                    query=user_query[:50],
                )

        except Exception as e:
            logger.error("dynamic_tool_load_failed", error=str(e))

        # Step 3: Log summary
        logger.info(
            "context_tools_prepared",
            total=len(result_schemas),
            core=len([s for s in result_schemas if is_core_tool(s.get("name", ""))]),
            dynamic=len(result_schemas)
            - len([s for s in result_schemas if is_core_tool(s.get("name", ""))]),
        )

        return result_schemas

    async def get_tools_by_names(
        self,
        tool_names: list[str],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get schemas for specific tool names.

        Useful for:
        - Re-loading tools after user correction
        - Loading tools from explicit user request
        - Fallback when search fails
        """
        schemas = []
        seen = set()

        for name in tool_names[:limit]:
            if name in seen:
                continue
            seen.add(name)

            # Check cache
            cached = _get_cached_schema(name)
            if cached:
                schemas.append(cached)

                continue

            # Not cached - get from JIT loader
            try:
                schema = self.jit_loader.get_tool_schema(name)
                if schema:
                    _cache_schema(name, schema)
                    schemas.append(schema)
            except Exception:
                _get_logger().warning("Failed to get schema", tool=name)

        return schemas

    async def get_relevant_memories(
        self,
        user_query: str,
        limit: int = 3,
    ) -> str:
        """
        Get relevant past experiences for context injection.

        Phase 71: The Memory Mesh - Retrieves similar past experiences
        to help the agent learn from previous interactions.

        Args:
            user_query: The current user query
            limit: Maximum memories to retrieve

        Returns:
            Formatted string of memories for context injection
        """
        global _cached_memory_interceptor

        if _cached_memory_interceptor is None:
            try:
                from agent.core.memory.interceptor import get_memory_interceptor

                _cached_memory_interceptor = get_memory_interceptor()
            except Exception:
                return ""

        try:
            memories = await _cached_memory_interceptor.before_execution(
                user_input=user_query,
                limit=limit,
            )

            if not memories:
                return ""

            # Format memories for context
            lines = ["## Relevant Past Experience:"]
            for i, m in enumerate(memories, 1):
                status = "✓" if m.outcome == "success" else "✗"
                lines.append(f"{i}. [{status}] {m.reflection}")

            return "\n".join(lines)

        except Exception as e:
            _get_logger().warning("Failed to get memories", error=str(e))
            return ""

    async def record_experience(
        self,
        user_query: str,
        tool_calls: list[str],
        success: bool,
        error: str | None = None,
    ) -> str | None:
        """
        Record a new experience to memory.

        Phase 71: Called after task execution to store the experience.

        Args:
            user_query: The original user query
            tool_calls: Tools that were called
            success: Whether the task succeeded
            error: Error message if failed

        Returns:
            ID of the created memory record
        """
        global _cached_memory_interceptor

        if _cached_memory_interceptor is None:
            try:
                from agent.core.memory.interceptor import get_memory_interceptor

                _cached_memory_interceptor = get_memory_interceptor()
            except Exception:
                return None

        try:
            return await _cached_memory_interceptor.after_execution(
                user_input=user_query,
                tool_calls=tool_calls,
                success=success,
                error=error,
            )
        except Exception as e:
            _get_logger().warning("Failed to record experience", error=str(e))
            return None


# =============================================================================
# Singleton Accessor
# =============================================================================


_loader: AdaptiveLoader | None = None


def get_adaptive_loader() -> AdaptiveLoader:
    """Get the AdaptiveLoader singleton."""
    global _loader
    if _loader is None:
        _loader = AdaptiveLoader()
    return _loader


# =============================================================================
# CLI Utility
# =============================================================================


async def debug_context_tools(query: str) -> None:
    """
    Debug utility to see what tools would be loaded for a query.

    Usage:
        python -c "import asyncio; asyncio.run(debug_context_tools('git commit'))"
    """
    loader = get_adaptive_loader()
    tools = await loader.get_context_tools(query)

    print(f"\n=== Context Tools for: '{query}' ===")
    print(f"Total tools: {len(tools)}\n")

    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")[:60]
        is_core = is_core_tool(name)
        marker = "[CORE]" if is_core else "[DYN]"
        print(f"{i:2}. {marker} {name}")
        print(f"    {desc}...")

    print()


__all__ = [
    "AdaptiveLoader",
    "get_adaptive_loader",
    "get_core_tools",
    "get_dynamic_tools_limit",
    "is_core_tool",
    "debug_context_tools",
]
