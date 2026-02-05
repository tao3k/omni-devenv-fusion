"""
executor.py - Command Execution Wrapper

Automatic response wrapping for command execution following Omni-Dev-Fusion
architecture improvements (Items 4 & 5).

Provides consistent error handling and response formatting for all command
executions through a unified executor interface.

Usage:
    from omni.core.executor import CommandExecutor
    from omni.core.responses import ToolResponse
    from omni.core.errors import OmniError, CoreErrorCode

    executor = CommandExecutor()

    # Execute with automatic response wrapping
    result: ToolResponse = await executor.execute(async_function, arg1=value1)

    # Execute with error mapping
    result = await executor.execute(
        risky_operation,
        error_map={
            FileNotFoundError: CoreErrorCode.STORAGE_NOT_FOUND,
            PermissionError: CoreErrorCode.PERMISSION_DENIED,
        }
    )
"""

import asyncio
from typing import Any, Callable, Optional, Type, TypeVar

from omni.core.errors import CoreErrorCode, OmniError
from omni.core.responses import ResponseStatus, ToolResponse


T = TypeVar("T")


class CommandExecutor:
    """Automatic response wrapper for command execution.

    Handles async/sync function execution with:
    - Consistent error handling and response formatting
    - Custom error code mapping
    - Detailed metadata collection
    - Support for both async and sync functions

    Attributes:
        default_metadata: Default metadata added to all responses
    """

    def __init__(
        self,
        default_metadata: Optional[dict[str, Any]] = None,
    ):
        """Initialize the executor.

        Args:
            default_metadata: Default metadata for all responses
        """
        self.default_metadata = default_metadata or {}

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        error_map: Optional[dict[Type[Exception], CoreErrorCode]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> ToolResponse:
        """Execute a function and wrap result in ToolResponse.

        Args:
            func: Function to execute (async or sync)
            *args: Positional arguments for the function
            error_map: Mapping from exception types to error codes
            metadata: Additional metadata for the response
            **kwargs: Keyword arguments for the function

        Returns:
            ToolResponse with success or error status
        """
        error_map = error_map or {}
        merged_metadata = {**self.default_metadata, **(metadata or {})}

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Return success response
            return ToolResponse.success(data=result, metadata=merged_metadata)

        except OmniError:
            # Re-raise OmniError subclasses (already properly formatted)
            raise

        except Exception as e:
            # Map exception to error code
            error_code = self._get_error_code(e, error_map)

            # Build error metadata
            error_metadata = {
                **merged_metadata,
                "error_type": type(e).__name__,
                "exception_message": str(e),
            }

            # Return error response
            return ToolResponse.error(
                message=str(e),
                code=error_code.value if error_code else None,
                metadata=error_metadata,
            )

    def _get_error_code(
        self,
        exception: Exception,
        error_map: dict[Type[Exception], CoreErrorCode],
    ) -> Optional[CoreErrorCode]:
        """Get error code for an exception.

        Args:
            exception: The exception that was raised
            error_map: Exception to error code mapping

        Returns:
            Mapped error code or None
        """
        # Direct match
        if type(exception) in error_map:
            return error_map[type(exception)]

        # Check parent classes
        for exc_type, code in error_map.items():
            if isinstance(exception, exc_type):
                return code

        return None


class AsyncCommandExecutor(CommandExecutor):
    """Async-specific command executor with enhanced features.

    Provides additional async-specific handling such as:
    - Timeout management
    - Cancellation handling
    - Task tracking
    """

    async def execute_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float,
        *args,
        error_map: Optional[dict[Type[Exception], CoreErrorCode]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> ToolResponse:
        """Execute with timeout protection.

        Args:
            func: Async function to execute
            timeout_seconds: Maximum execution time in seconds
            *args: Positional arguments for the function
            error_map: Exception to error code mapping
            metadata: Additional metadata for the response
            **kwargs: Keyword arguments for the function

        Returns:
            ToolResponse with success or timeout error
        """
        error_map = error_map or {}
        merged_metadata = {**self.default_metadata, **(metadata or {})}

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout_seconds,
            )
            return ToolResponse.success(data=result, metadata=merged_metadata)

        except asyncio.TimeoutError:
            return ToolResponse.error(
                message=f"Operation timed out after {timeout_seconds} seconds",
                code=CoreErrorCode.TOOL_TIMEOUT.value,
                metadata={
                    **merged_metadata,
                    "timeout_seconds": timeout_seconds,
                },
            )

        except OmniError:
            raise

        except Exception as e:
            error_code = self._get_error_code(e, error_map)
            error_metadata = {
                **merged_metadata,
                "error_type": type(e).__name__,
                "exception_message": str(e),
            }
            return ToolResponse.error(
                message=str(e),
                code=error_code.value if error_code else None,
                metadata=error_metadata,
            )


def wrap_result(
    result: Any,
    metadata: Optional[dict[str, Any]] = None,
) -> ToolResponse:
    """Wrap a raw result in ToolResponse.

    Convenience function for simple result wrapping.

    Args:
        result: The result to wrap
        metadata: Optional metadata

    Returns:
        ToolResponse with the result as data
    """
    return ToolResponse.success(data=result, metadata=metadata)


def wrap_error(
    message: str,
    code: Optional[CoreErrorCode] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ToolResponse:
    """Create an error response.

    Convenience function for creating error responses.

    Args:
        message: Error message
        code: Error code
        metadata: Optional metadata

    Returns:
        ToolResponse with error status
    """
    return ToolResponse.error(message=message, code=code.value if code else None, metadata=metadata)


def wrap_blocked(
    reason: str,
    metadata: Optional[dict[str, Any]] = None,
) -> ToolResponse:
    """Create a blocked response.

    Convenience function for creating blocked responses.

    Args:
        reason: Reason for blocking
        metadata: Optional metadata

    Returns:
        ToolResponse with blocked status
    """
    return ToolResponse.blocked(reason=reason, metadata=metadata)
