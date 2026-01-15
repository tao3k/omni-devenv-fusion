"""
agent/core/memory/interceptor.py
 The Memory Mesh - Runtime Memory Interceptor

Automatically captures and records agent experiences during execution.

Usage:
    from agent.core.memory.interceptor import get_memory_interceptor

    interceptor = get_memory_interceptor()

    # Before execution: inject relevant memories
    memories = await interceptor.before_execution(user_input)

    # After execution: record the experience
    await interceptor.after_execution(
        user_input=user_input,
        tool_calls=["git.commit"],
        success=False,
        error="lock file exists"
    )
"""

from __future__ import annotations

import structlog
from typing import Any, List, Optional

from .manager import get_memory_manager
from .types import InteractionLog

# Lazy logger
_cached_logger: Any = None


def _get_logger() -> Any:
    global _cached_logger
    if _cached_logger is None:
        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class MemoryInterceptor:
    """
    Runtime interceptor for automatic memory capture and injection.

    Intercepts agent execution to:
    1. BEFORE: Retrieve relevant past experiences for context injection
    2. AFTER: Record new experiences with auto-generated reflections
    """

    def __init__(self) -> None:
        """Initialize the memory interceptor."""
        self._manager = get_memory_manager()
        self._session_id: str | None = None

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for memory grouping."""
        self._session_id = session_id

    async def before_execution(
        self,
        user_input: str,
        limit: int = 3,
    ) -> List[InteractionLog]:
        """
        Retrieve relevant memories before task execution.

        Called by AdaptiveLoader to inject historical context.

        Args:
            user_input: The user's current query/intent
            limit: Maximum memories to retrieve

        Returns:
            List of relevant InteractionLog objects
        """
        try:
            memories = await self._manager.recall(
                query=user_input,
                limit=limit,
            )

            if memories:
                _get_logger().debug(
                    "Memory context loaded",
                    query=user_input[:50],
                    memories=len(memories),
                )

            return memories

        except Exception as e:
            _get_logger().warning("Failed to retrieve memories", error=str(e))
            return []

    async def after_execution(
        self,
        user_input: str,
        tool_calls: List[str],
        success: bool,
        error: Optional[str] = None,
        reflection: Optional[str] = None,
    ) -> str | None:
        """
        Record experience after task execution.

        Automatically generates a reflection if not provided.

        Args:
            user_input: The original user query
            tool_calls: List of tools that were called
            success: Whether the task succeeded
            error: Error message if failed
            reflection: Optional pre-generated reflection

        Returns:
            The ID of the created memory record
        """
        try:
            # Auto-generate reflection if not provided
            if reflection is None:
                reflection = self._generate_reflection(
                    user_input=user_input,
                    success=success,
                    error=error,
                    tool_calls=tool_calls,
                )

            # Record to memory
            record_id = await self._manager.add_experience(
                user_query=user_input,
                tool_calls=tool_calls,
                outcome="success" if success else "failure",
                reflection=reflection,
                error_msg=error,
                session_id=self._session_id,
            )

            if record_id:
                _get_logger().info(
                    "Experience recorded",
                    id=record_id,
                    outcome="success" if success else "failure",
                )

            return record_id

        except Exception as e:
            _get_logger().error("Failed to record experience", error=str(e))
            return None

    def _generate_reflection(
        self,
        user_input: str,
        success: bool,
        error: Optional[str],
        tool_calls: List[str],
    ) -> str:
        """
        Automatically generate a reflection based on execution result.

        This is a simple template-based generator. For more sophisticated
        reflections, this could be enhanced with LLM calls.

        Args:
            user_input: Original user query
            success: Whether the task succeeded
            error: Error message if failed
            tool_calls: Tools that were called

        Returns:
            Generated reflection string
        """
        if success:
            # Success reflection - summarize what worked
            tools_str = ", ".join(tool_calls) if tool_calls else "no tools"
            return f"Successfully completed: {user_input[:100]}. Used tools: {tools_str}."
        else:
            # Failure reflection - summarize what went wrong and hint at solution
            if error:
                # Extract key error info
                error_lower = error.lower()
                if "lock" in error_lower:
                    suggestion = "Try removing the lock file (.git/index.lock) before retrying."
                elif "permission" in error_lower:
                    suggestion = "Check file permissions or run with appropriate access."
                elif "not found" in error_lower:
                    suggestion = "Verify the file/path exists before accessing."
                elif "timeout" in error_lower:
                    suggestion = "Consider increasing timeout or breaking into smaller operations."
                else:
                    suggestion = "Review the error message for specific guidance."

                return f"Failed: {user_input[:80]}. Error: {error[:100]}. {suggestion}"
            else:
                return f"Failed: {user_input[:100]}. No specific error message provided."


# Singleton instance
_interceptor: MemoryInterceptor | None = None


def get_memory_interceptor() -> MemoryInterceptor:
    """Get the singleton MemoryInterceptor instance."""
    global _interceptor
    if _interceptor is None:
        _interceptor = MemoryInterceptor()
    return _interceptor


def format_memories_for_context(memories: List[InteractionLog]) -> str:
    """
    Format memories as a context string for LLM injection.

    Args:
        memories: List of interaction logs

    Returns:
        Formatted string suitable for context injection
    """
    if not memories:
        return ""

    lines = ["## Relevant Past Experience:"]
    for i, m in enumerate(memories, 1):
        status = "✓" if m.outcome == "success" else "✗"
        lines.append(f"{i}. [{status}] {m.reflection}")

    return "\n".join(lines)


__all__ = [
    "MemoryInterceptor",
    "get_memory_interceptor",
    "format_memories_for_context",
    "InteractionLog",
]
