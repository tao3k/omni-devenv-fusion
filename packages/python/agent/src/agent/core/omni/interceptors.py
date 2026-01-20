"""
interceptors.py - Tool Call Interceptors.

Interceptor Pattern for tool call validation and optimization:
- ActionGuard: Prevents redundant operations (e.g., repeated file reads)
- Provides warning messages that guide the agent back on track

Usage:
    guard = ActionGuard(state)
    warning = guard.check(tool_name, tool_input)
    if warning:
        # Handle warning - skip execution and return warning to LLM
"""

from __future__ import annotations

import structlog
from typing import Any, Optional

from agent.core.omni.state import LoopState

logger = structlog.get_logger(__name__)


class ActionGuard:
    """
    Interceptor that validates and optimizes tool calls.

    Responsibilities:
    - Detect redundant operations (e.g., reading same file twice)
    - Provide actionable warning messages
    - Update state based on tool execution
    """

    def __init__(self, state: LoopState) -> None:
        self._state = state

    def check(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """
        Check if a tool call should be blocked or warned about.

        Args:
            tool_name: Name of the tool being called
            tool_input: Arguments passed to the tool

        Returns:
            Warning message if action is problematic, None if OK
        """
        # Check for redundant file reads
        if "read_file" in tool_name or tool_name == "terminal":
            path = self._extract_file_path(tool_name, tool_input)
            if path and self._state.is_redundant_read(path):
                logger.warning(f"ActionGuard: Blocking repeat read of {path}")
                return self._block_message(path)

        return None

    def update_state(self, tool_name: str, tool_input: dict) -> None:
        """Update state after tool execution."""
        path = self._extract_file_path(tool_name, tool_input)
        if not path:
            return

        # Track file reads
        if "read_file" in tool_name:
            self._state.mark_read(path)

        # Track file modifications
        if any(
            x in tool_name for x in ["write_file", "save_file", "apply_changes", "replace", "edit"]
        ):
            self._state.mark_modified(path)

    def _extract_file_path(self, tool_name: str, tool_input: Any) -> str:
        """
        Extract file path from tool input.

        Handles different input formats:
        - {'file_path': '...'} (most common)
        - {'path': '...'}
        - {'command': 'cat file.txt'} (terminal)
        """
        if not isinstance(tool_input, dict):
            return str(tool_input) if tool_input else ""

        # Try common fields
        path = tool_input.get("file_path", "") or tool_input.get("path", "")

        # For terminal commands, extract from command string
        if not path and tool_name == "terminal":
            command = tool_input.get("command", "")
            if command:
                # Simple extraction: look for file paths after common commands
                if "cat " in command:
                    path = command.split("cat ", 1)[1].split()[0] if " " in command else command

        return path.strip().lstrip("./")

    def _block_message(self, file_path: str) -> str:
        """Generate a warning message for blocked actions."""
        return (
            f"[BLOCKED - REPEAT READ]\n"
            f"You already read '{file_path}' in a previous step.\n"
            f"The content is in your context history above.\n\n"
            f"IMMEDIATE ACTION: Use 'filesystem.write_file' or similar tool to modify the file.\n"
            f"Do not re-read this file unless you have already modified it."
        )


class NoOpGuard:
    """A guard that does nothing - used for testing or when guards are disabled."""

    def check(self, tool_name: str, tool_input: dict) -> Optional[str]:
        return None

    def update_state(self, tool_name: str, tool_input: dict) -> None:
        pass


__all__ = ["ActionGuard", "NoOpGuard", "LoopState"]
