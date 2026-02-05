"""
errors.py - Error Code System

Comprehensive error code system for Omni-Dev-Fusion following architecture
improvements (Items 4 & 5).

Error Code Structure:
- 1xxx: Validation errors
- 2xxx: Security errors
- 3xxx: Runtime errors
- 4xxx: Storage errors
- 5xxx: OmniCell errors
- 9xxx: Third-party/External errors

Usage:
    from omni.core.errors import OmniError, CoreErrorCode, ErrorCategory

    raise OmniError(
        message="Tool not found",
        code=CoreErrorCode.TOOL_NOT_FOUND,
        category=ErrorCategory.RUNTIME,
        details={"tool": "git.commit"}
    )
"""

from enum import Enum
from typing import Any, Optional


class ErrorCategory(str, Enum):
    """Error category classification."""

    VALIDATION = "VALIDATION"
    SECURITY = "SECURITY"
    RUNTIME = "RUNTIME"
    NETWORK = "NETWORK"
    STORAGE = "STORAGE"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


def _infer_category_from_code(code: str) -> ErrorCategory:
    """Infer error category from error code prefix.

    Args:
        code: Error code string (e.g., "3001")

    Returns:
        Inferred ErrorCategory
    """
    if not code or len(code) < 2:
        return ErrorCategory.UNKNOWN

    prefix = code[0]
    category_map = {
        "1": ErrorCategory.VALIDATION,
        "2": ErrorCategory.SECURITY,
        "3": ErrorCategory.RUNTIME,
        "4": ErrorCategory.STORAGE,
        "5": ErrorCategory.RUNTIME,  # OmniCell errors are runtime
        "9": ErrorCategory.EXTERNAL,
    }
    return category_map.get(prefix, ErrorCategory.UNKNOWN)


class CoreErrorCode(str, Enum):
    """Core error codes for Omni-Dev-Fusion.

    Format: Category letter + 3-digit sequence
    - 1xxx: Validation errors
    - 2xxx: Security errors
    - 3xxx: Runtime errors
    - 4xxx: Storage errors
    - 5xxx: OmniCell errors
    - 9xxx: External errors
    """

    # ==========================================================================
    # Validation Errors (1xxx)
    # ==========================================================================
    INVALID_ARGUMENT = "1001"
    MISSING_REQUIRED = "1002"
    TYPE_MISMATCH = "1003"
    VALUE_OUT_OF_RANGE = "1004"
    FORMAT_ERROR = "1005"

    # ==========================================================================
    # Security Errors (2xxx)
    # ==========================================================================
    UNAUTHORIZED = "2001"
    FORBIDDEN = "2002"
    RATE_LIMITED = "2003"
    SECURITY_CHECK_FAILED = "2004"
    MALICIOUS_INPUT = "2005"
    PERMISSION_DENIED = "2006"

    # ==========================================================================
    # Runtime Errors (3xxx)
    # ==========================================================================
    TOOL_NOT_FOUND = "3001"
    TOOL_EXECUTION_FAILED = "3002"
    TOOL_TIMEOUT = "3003"
    COMMAND_BLOCKED = "3004"
    INVALID_STATE = "3005"
    DEPENDENCY_MISSING = "3006"
    CIRCULAR_DEPENDENCY = "3007"

    # ==========================================================================
    # Storage Errors (4xxx)
    # ==========================================================================
    STORAGE_READ_ERROR = "4001"
    STORAGE_WRITE_ERROR = "4002"
    STORAGE_NOT_FOUND = "4003"
    STORAGE_CORRUPTION = "4004"

    # ==========================================================================
    # OmniCell Errors (5xxx)
    # ==========================================================================
    CELL_EXECUTION_ERROR = "5001"
    CELL_JSON_DECODE_ERROR = "5002"
    CELL_SUBPROCESS_ERROR = "5003"
    CELL_CLASSIFICATION_ERROR = "5004"
    CELL_SECURITY_REJECTED = "5005"

    # ==========================================================================
    # External/Third-party Errors (9xxx)
    # ==========================================================================
    EXTERNAL_API_ERROR = "9001"
    EXTERNAL_TIMEOUT = "9002"
    EXTERNAL_UNAVAILABLE = "9003"


class OmniError(Exception):
    """Base exception for Omni-Dev-Fusion errors.

    All project-specific exceptions should inherit from this class.
    Provides structured error information with code, category, and details.

    Attributes:
        message: Human-readable error description
        code: Error code from CoreErrorCode
        category: Error category from ErrorCategory
        details: Additional error context dictionary
    """

    def __init__(
        self,
        message: str,
        code: Optional[CoreErrorCode] = None,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize OmniError.

        Args:
            message: Human-readable error description
            code: Error code from CoreErrorCode enum
            category: Error category from ErrorCategory enum
            details: Additional error context
        """
        self.message = message
        self.code = code

        # Infer category from code if not provided
        if category == ErrorCategory.UNKNOWN and code:
            code_str = code.value if hasattr(code, "value") else str(code)
            category = _infer_category_from_code(code_str)

        self.category = category
        self.details = details or {}

        # Format error string with code prefix
        code_str = code.value if hasattr(code, "value") else (code if code else "UNKNOWN")
        super().__init__(f"[{code_str}] {message}")

    def __str__(self) -> str:
        """Return formatted error string with code prefix."""
        code_str = (
            self.code.value
            if hasattr(self.code, "value")
            else (self.code if self.code else "UNKNOWN")
        )
        return f"[{code_str}] {self.message}"

    def __repr__(self) -> str:
        """Return detailed error representation."""
        return (
            f"OmniError(message={self.message!r}, "
            f"code={self.code.value if self.code else None!r}, "
            f"category={self.category.value!r}, "
            f"details={self.details!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary format.

        Returns:
            Dictionary representation of the error
        """
        return {
            "message": self.message,
            "code": self.code.value if self.code else None,
            "category": self.category.value,
            "details": self.details,
        }


class ValidationError(OmniError):
    """Exception for validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize ValidationError.

        Args:
            message: Error message
            field: Name of the field that failed validation
            value: The invalid value
            details: Additional context
        """
        extra_details = {"field": field, "value": value}
        if details:
            extra_details.update(details)

        super().__init__(
            message=message,
            code=CoreErrorCode.INVALID_ARGUMENT,
            category=ErrorCategory.VALIDATION,
            details=extra_details,
        )


class SecurityError(OmniError):
    """Exception for security-related errors."""

    def __init__(
        self,
        message: str,
        check_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize SecurityError.

        Args:
            message: Security error description
            check_type: Type of security check that failed
            details: Additional context
        """
        extra_details = {"check_type": check_type}
        if details:
            extra_details.update(details)

        super().__init__(
            message=message,
            code=CoreErrorCode.SECURITY_CHECK_FAILED,
            category=ErrorCategory.SECURITY,
            details=extra_details,
        )


class ToolNotFoundError(OmniError):
    """Exception when a tool is not found."""

    def __init__(
        self,
        tool_name: str,
        available_tools: Optional[list[str]] = None,
    ):
        """Initialize ToolNotFoundError.

        Args:
            tool_name: Name of the tool that was not found
            available_tools: List of available tool names
        """
        details = {"tool": tool_name}
        if available_tools:
            details["available_tools"] = available_tools

        super().__init__(
            message=f"Tool not found: {tool_name}",
            code=CoreErrorCode.TOOL_NOT_FOUND,
            category=ErrorCategory.RUNTIME,
            details=details,
        )


class ToolExecutionError(OmniError):
    """Exception when tool execution fails."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize ToolExecutionError.

        Args:
            tool_name: Name of the tool that failed
            message: Error description
            exit_code: Process exit code if applicable
            stderr: Standard error output if applicable
            details: Additional context
        """
        extra_details = {
            "tool": tool_name,
            "exit_code": exit_code,
            "stderr": stderr,
        }
        if details:
            extra_details.update(details)

        super().__init__(
            message=f"Tool execution failed: {message}",
            code=CoreErrorCode.TOOL_EXECUTION_FAILED,
            category=ErrorCategory.RUNTIME,
            details=extra_details,
        )


class OmniCellError(OmniError):
    """Exception for OmniCell execution errors."""

    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        error_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        """Initialize OmniCellError.

        Args:
            message: Error description
            command: The command that failed
            error_type: Type of error (json_decode, subprocess, etc.)
            details: Additional context
        """
        extra_details = {
            "command": command,
            "error_type": error_type,
        }
        if details:
            extra_details.update(details)

        super().__init__(
            message=message,
            code=CoreErrorCode.CELL_EXECUTION_ERROR,
            category=ErrorCategory.RUNTIME,
            details=extra_details,
        )


def get_error_code_description(code: CoreErrorCode) -> str:
    """Get human-readable description for an error code.

    Args:
        code: The error code to describe

    Returns:
        Human-readable description of the error code
    """
    descriptions = {
        # Validation (1xxx)
        CoreErrorCode.INVALID_ARGUMENT: "Invalid argument provided",
        CoreErrorCode.MISSING_REQUIRED: "Required argument is missing",
        CoreErrorCode.TYPE_MISMATCH: "Type mismatch in argument",
        CoreErrorCode.VALUE_OUT_OF_RANGE: "Value is out of valid range",
        CoreErrorCode.FORMAT_ERROR: "Format error in input",
        # Security (2xxx)
        CoreErrorCode.UNAUTHORIZED: "Authentication required",
        CoreErrorCode.FORBIDDEN: "Access forbidden",
        CoreErrorCode.RATE_LIMITED: "Rate limit exceeded",
        CoreErrorCode.SECURITY_CHECK_FAILED: "Security check failed",
        CoreErrorCode.MALICIOUS_INPUT: "Malicious input detected",
        CoreErrorCode.PERMISSION_DENIED: "Permission denied",
        # Runtime (3xxx)
        CoreErrorCode.TOOL_NOT_FOUND: "Tool not found",
        CoreErrorCode.TOOL_EXECUTION_FAILED: "Tool execution failed",
        CoreErrorCode.TOOL_TIMEOUT: "Tool execution timed out",
        CoreErrorCode.COMMAND_BLOCKED: "Command was blocked",
        CoreErrorCode.INVALID_STATE: "Invalid state encountered",
        CoreErrorCode.DEPENDENCY_MISSING: "Required dependency is missing",
        CoreErrorCode.CIRCULAR_DEPENDENCY: "Circular dependency detected",
        # Storage (4xxx)
        CoreErrorCode.STORAGE_READ_ERROR: "Failed to read from storage",
        CoreErrorCode.STORAGE_WRITE_ERROR: "Failed to write to storage",
        CoreErrorCode.STORAGE_NOT_FOUND: "Storage resource not found",
        CoreErrorCode.STORAGE_CORRUPTION: "Storage corruption detected",
        # OmniCell (5xxx)
        CoreErrorCode.CELL_EXECUTION_ERROR: "OmniCell execution error",
        CoreErrorCode.CELL_JSON_DECODE_ERROR: "JSON decode error in OmniCell",
        CoreErrorCode.CELL_SUBPROCESS_ERROR: "Subprocess error in OmniCell",
        CoreErrorCode.CELL_CLASSIFICATION_ERROR: "Command classification error",
        CoreErrorCode.CELL_SECURITY_REJECTED: "Command rejected by security check",
        # External (9xxx)
        CoreErrorCode.EXTERNAL_API_ERROR: "External API error",
        CoreErrorCode.EXTERNAL_TIMEOUT: "External service timeout",
        CoreErrorCode.EXTERNAL_UNAVAILABLE: "External service unavailable",
    }
    return descriptions.get(code, "Unknown error")
