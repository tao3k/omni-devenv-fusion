"""
mcp_core/protocols.py
Phase 29: Protocol-based design for mcp_core modules.

Provides Protocol definitions for type-safe, testable code.
All major components implement these protocols for mocking capability.

Usage:
    from mcp_core.protocols import ILazyCache, ISafeExecutor, IInferenceClient

    # For testing, mock the protocol
    from unittest.mock import MagicMock
    mock_cache: ILazyCache[str] = MagicMock()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Generic,
    TypeVar,
    Protocol,
    runtime_checkable,
)

# Type aliases (PEP 695)
type ContextData = dict[str, Any]
type CacheValue = str | ContextData
type ConfigValue = str | int | bool | list[str] | None

# =============================================================================
# Lazy Cache Protocols
# =============================================================================

T = TypeVar("T", bound=CacheValue)


@runtime_checkable
class ILazyCache(Protocol[T]):
    """Protocol for lazy-loading singleton caches."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def get(self) -> T: ...

    @abstractmethod
    def reload(self) -> T: ...

    @classmethod
    @abstractmethod
    def reset(cls) -> None: ...


@runtime_checkable
class IFileCache(Protocol):
    """Protocol for file content caching."""

    @property
    @abstractmethod
    def content(self) -> str: ...

    @abstractmethod
    def get(self) -> str: ...


@runtime_checkable
class IConfigCache(Protocol):
    """Protocol for configuration file caching."""

    @abstractmethod
    def get(self) -> ContextData: ...


# =============================================================================
# Settings Protocols
# =============================================================================


@runtime_checkable
class ISettings(Protocol):
    """Protocol for project settings management."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def get_path(self, key: str) -> str: ...

    @abstractmethod
    def get_list(self, key: str) -> list[str]: ...

    @abstractmethod
    def has_setting(self, key: str) -> bool: ...

    @abstractmethod
    def get_section(self, section: str) -> ContextData: ...

    @abstractmethod
    def list_sections(self) -> list[str]: ...

    @abstractmethod
    def reload(self) -> None: ...

    @property
    @abstractmethod
    def conf_dir(self) -> str: ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...


# =============================================================================
# Execution Protocols
# =============================================================================


@runtime_checkable
class ISafeExecutor(Protocol):
    """Protocol for safe command execution."""

    @staticmethod
    @abstractmethod
    async def run(
        command: str,
        args: list[str] | None = None,
        allowed_commands: dict[str, list[str]] | None = None,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> dict[str, Any]: ...

    @staticmethod
    @abstractmethod
    async def run_sandbox(
        command: str,
        args: list[str] | None = None,
        timeout: int = 60,
        # NOTE: read_only and sandbox_env are reserved for future sandbox implementation
        read_only: bool = False,
        sandbox_env: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    @staticmethod
    @abstractmethod
    def format_result(
        result: dict[str, Any], command: str, args: list[str] | None = None
    ) -> str: ...


# =============================================================================
# Inference Protocols
# =============================================================================


@runtime_checkable
class IInferenceClient(Protocol):
    """Protocol for LLM inference client."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def stream_complete(
        self,
        system_prompt: str,
        user_query: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]: ...

    @abstractmethod
    async def complete_with_retry(
        self,
        system_prompt: str,
        user_query: str,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def get_tool_schema(self, skill_names: list[str] | None = None) -> list[dict]: ...


# =============================================================================
# Context Protocols
# =============================================================================


@runtime_checkable
class IProjectContext(Protocol):
    """Protocol for project-specific context."""

    @property
    @abstractmethod
    def lang_id(self) -> str: ...

    @property
    @abstractmethod
    def categories(self) -> list[str]: ...

    @abstractmethod
    def get(self, category: str | None = None) -> str: ...

    @abstractmethod
    def has_category(self, category: str) -> bool: ...


@runtime_checkable
class IContextRegistry(Protocol):
    """Protocol for context registry."""

    @abstractmethod
    def register(self, context: IProjectContext) -> None: ...

    @abstractmethod
    def get(self, lang_id: str) -> IProjectContext | None: ...

    @abstractmethod
    def list_registered(self) -> list[str]: ...

    @abstractmethod
    def has(self, lang_id: str) -> bool: ...


# =============================================================================
# Base Dataclasses (with slots=True for memory efficiency)
# =============================================================================


from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class ExecutionResult:
    """Result of command execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    error: str = ""


@dataclass(slots=True)
class InferenceResult:
    """Result of LLM inference."""

    success: bool
    content: str = ""
    tool_calls: list[dict[str, Any]] = None  # type: ignore[assignment]
    model: str = ""
    usage: dict[str, int] = None  # type: ignore[assignment]
    error: str = ""

    def __post_init__(self) -> None:
        if self.tool_calls is None:
            self.tool_calls = []
        if self.usage is None:
            self.usage = {}


@dataclass(slots=True)
class CacheEntry:
    """Entry for cache storage."""

    value: CacheValue
    created_at: float = 0.0
    version: int = 0


@dataclass(slots=True)
class PathSafetyResult:
    """Result of path safety check."""

    is_safe: bool
    error_message: str = ""


@dataclass(slots=True)
class SettingsEntry:
    """Entry for settings storage."""

    value: ConfigValue
    source: str = "default"


# =============================================================================
# Utility Protocols
# =============================================================================


@runtime_checkable
class IPathSafety(Protocol):
    """Protocol for path safety checking."""

    @staticmethod
    @abstractmethod
    def is_safe_path(
        path: str,
        project_root: Path | None = None,
        blocked_dirs: set[str] | None = None,
        allow_hidden: bool = True,
        allowed_hidden_files: set[str] | None = None,
    ) -> tuple[bool, str]: ...

    @staticmethod
    @abstractmethod
    def is_safe_command(
        command: str, allowed_commands: dict[str, list[str]] | None = None
    ) -> tuple[bool, str]: ...


@runtime_checkable
class IEnvironmentLoader(Protocol):
    """Protocol for environment variable loading."""

    @staticmethod
    @abstractmethod
    def load_env_from_file(
        config_key: str | None = None,
        env_key: str | None = None,
        config_file: str | None = None,
    ) -> dict[str, str]: ...

    @staticmethod
    @abstractmethod
    def get_env(
        key: str, env_vars: dict[str, str] | None = None, default: str | None = None
    ) -> str: ...


# =============================================================================
# Logger Protocol
# =============================================================================


class IMCPLogger(Protocol):
    """Protocol for structured logging."""

    @abstractmethod
    def debug(self, event: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def info(self, event: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def warning(self, event: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def error(self, event: str, **kwargs: Any) -> None: ...


# =============================================================================
# Export
# =============================================================================


__all__ = [
    # Type aliases
    "ContextData",
    "CacheValue",
    "ConfigValue",
    # Lazy Cache Protocols
    "ILazyCache",
    "IFileCache",
    "IConfigCache",
    # Settings Protocols
    "ISettings",
    # Execution Protocols
    "ISafeExecutor",
    # Inference Protocols
    "IInferenceClient",
    # Context Protocols
    "IProjectContext",
    "IContextRegistry",
    # Utility Protocols
    "IPathSafety",
    "IEnvironmentLoader",
    # Logger Protocol
    "IMCPLogger",
    # Base Dataclasses
    "ExecutionResult",
    "InferenceResult",
    "CacheEntry",
    "PathSafetyResult",
    "SettingsEntry",
]
