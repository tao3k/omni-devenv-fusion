"""
responses.py - Unified MCP Tool Response Format

Standardized response format for all MCP Tools following Omni-Dev-Fusion
architecture improvements (Items 4 & 5).

Usage:
    from omni.core.responses import ToolResponse, ResponseStatus

    # Success response
    return ToolResponse.success(data={"key": "value"})

    # Error response
    return ToolResponse.error("Not found", code=CoreErrorCode.TOOL_NOT_FOUND)

    # Blocked response
    return ToolResponse.blocked("Security check failed")
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    """Standardized response status values."""

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    PARTIAL = "partial"


class ToolResponse(BaseModel):
    """Unified MCP Tool Response Format.

    All MCP tools should return responses in this standardized format.
    Provides consistent structure for success, error, and blocked states.

    Attributes:
        status: Response status (success, error, blocked, partial)
        data: Response payload (optional)
        error_message: Error message (only for error status)
        error_code: Machine-readable error code (only for error status)
        metadata: Additional context information
        timestamp: Response creation timestamp
    """

    status: ResponseStatus = Field(..., description="Response status")
    data: Optional[Any] = Field(
        default=None, description="Response payload for successful operations"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message for failed operations"
    )
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context information"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response timestamp",
    )

    def to_mcp(self) -> list[dict]:
        """Convert to MCP protocol format.

        Returns:
            List containing a single text content block with JSON response
        """
        return [{"type": "text", "text": self.model_dump_json()}]

    @classmethod
    def success(cls, data: Any = None, metadata: Optional[dict] = None) -> "ToolResponse":
        """Create a success response.

        Args:
            data: Response payload
            metadata: Optional additional context

        Returns:
            ToolResponse with success status
        """
        return cls(
            status=ResponseStatus.SUCCESS,
            data=data,
            metadata=metadata or {},
        )

    @classmethod
    def error(
        cls,
        message: str,
        code: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResponse":
        """Create an error response.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            metadata: Optional additional context

        Returns:
            ToolResponse with error status
        """
        return cls(
            status=ResponseStatus.ERROR,
            error_message=message,
            error_code=code,
            metadata=metadata or {},
        )

    @classmethod
    def blocked(
        cls,
        reason: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResponse":
        """Create a blocked response (e.g., security check failed).

        Args:
            reason: Reason for blocking the operation
            metadata: Optional additional context

        Returns:
            ToolResponse with blocked status
        """
        return cls(
            status=ResponseStatus.BLOCKED,
            error_message=reason,
            error_code="BLOCKED",
            metadata=metadata or {},
        )

    @classmethod
    def partial(
        cls,
        data: Any = None,
        message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResponse":
        """Create a partial success response.

        Used when operation succeeded but with limitations or partial results.

        Args:
            data: Partial response data
            message: Description of what was partial
            metadata: Optional additional context

        Returns:
            ToolResponse with partial status
        """
        return cls(
            status=ResponseStatus.PARTIAL,
            data=data,
            error_message=message,
            metadata=metadata or {},
        )

    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.status == ResponseStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """Check if response is an error."""
        return self.status == ResponseStatus.ERROR

    @property
    def is_blocked(self) -> bool:
        """Check if response is blocked."""
        return self.status == ResponseStatus.BLOCKED
