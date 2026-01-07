"""
execution/protocols.py
Protocol definitions for execution module.

Phase 29: Protocol-based design for testability.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ISafeExecutor(Protocol):
    """Protocol for safe command execution."""

    @staticmethod
    async def run(
        command: str,
        args: list[str] | None = None,
        allowed_commands: dict[str, list[str]] | None = None,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> dict[str, Any]: ...

    @staticmethod
    async def run_sandbox(
        command: str,
        args: list[str] | None = None,
        timeout: int = 60,
        read_only: bool = False,
        sandbox_env: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    @staticmethod
    def format_result(
        result: dict[str, Any], command: str, args: list[str] | None = None
    ) -> str: ...


@runtime_checkable
class ISecurityChecker(Protocol):
    """Protocol for security checking."""

    @staticmethod
    def check_dangerous_patterns(command: str, args: list[str]) -> tuple[bool, str]: ...

    @staticmethod
    def check_whitelist(
        command: str, args: list[str], allowed_commands: dict[str, list[str]] | None = None
    ) -> tuple[bool, str]: ...


__all__ = ["ISafeExecutor", "ISecurityChecker"]
