"""
test_errors.py - Unit tests for error code system

Tests for OmniError exception and CoreErrorCode enum.
"""

import pytest

from omni.core.errors import (
    CoreErrorCode,
    ErrorCategory,
    OmniCellError,
    OmniError,
    SecurityError,
    ToolExecutionError,
    ToolNotFoundError,
    ValidationError,
    get_error_code_description,
)


class TestCoreErrorCode:
    """Tests for CoreErrorCode enum."""

    def test_validation_codes(self):
        """Test validation error codes."""
        assert CoreErrorCode.INVALID_ARGUMENT == "1001"
        assert CoreErrorCode.MISSING_REQUIRED == "1002"
        assert CoreErrorCode.TYPE_MISMATCH == "1003"
        assert CoreErrorCode.VALUE_OUT_OF_RANGE == "1004"
        assert CoreErrorCode.FORMAT_ERROR == "1005"

    def test_security_codes(self):
        """Test security error codes."""
        assert CoreErrorCode.UNAUTHORIZED == "2001"
        assert CoreErrorCode.FORBIDDEN == "2002"
        assert CoreErrorCode.RATE_LIMITED == "2003"
        assert CoreErrorCode.SECURITY_CHECK_FAILED == "2004"
        assert CoreErrorCode.MALICIOUS_INPUT == "2005"
        assert CoreErrorCode.PERMISSION_DENIED == "2006"

    def test_runtime_codes(self):
        """Test runtime error codes."""
        assert CoreErrorCode.TOOL_NOT_FOUND == "3001"
        assert CoreErrorCode.TOOL_EXECUTION_FAILED == "3002"
        assert CoreErrorCode.TOOL_TIMEOUT == "3003"
        assert CoreErrorCode.COMMAND_BLOCKED == "3004"
        assert CoreErrorCode.INVALID_STATE == "3005"
        assert CoreErrorCode.DEPENDENCY_MISSING == "3006"
        assert CoreErrorCode.CIRCULAR_DEPENDENCY == "3007"

    def test_storage_codes(self):
        """Test storage error codes."""
        assert CoreErrorCode.STORAGE_READ_ERROR == "4001"
        assert CoreErrorCode.STORAGE_WRITE_ERROR == "4002"
        assert CoreErrorCode.STORAGE_NOT_FOUND == "4003"
        assert CoreErrorCode.STORAGE_CORRUPTION == "4004"

    def test_omnicell_codes(self):
        """Test OmniCell error codes."""
        assert CoreErrorCode.CELL_EXECUTION_ERROR == "5001"
        assert CoreErrorCode.CELL_JSON_DECODE_ERROR == "5002"
        assert CoreErrorCode.CELL_SUBPROCESS_ERROR == "5003"
        assert CoreErrorCode.CELL_CLASSIFICATION_ERROR == "5004"
        assert CoreErrorCode.CELL_SECURITY_REJECTED == "5005"

    def test_external_codes(self):
        """Test external error codes."""
        assert CoreErrorCode.EXTERNAL_API_ERROR == "9001"
        assert CoreErrorCode.EXTERNAL_TIMEOUT == "9002"
        assert CoreErrorCode.EXTERNAL_UNAVAILABLE == "9003"

    def test_error_code_is_string(self):
        """Test that error codes are strings."""
        assert isinstance(CoreErrorCode.TOOL_NOT_FOUND.value, str)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert ErrorCategory.VALIDATION == "VALIDATION"
        assert ErrorCategory.SECURITY == "SECURITY"
        assert ErrorCategory.RUNTIME == "RUNTIME"
        assert ErrorCategory.NETWORK == "NETWORK"
        assert ErrorCategory.STORAGE == "STORAGE"
        assert ErrorCategory.EXTERNAL == "EXTERNAL"
        assert ErrorCategory.UNKNOWN == "UNKNOWN"


class TestOmniError:
    """Tests for base OmniError exception."""

    def test_basic_error(self):
        """Test creating a basic OmniError."""
        error = OmniError(message="Something went wrong")
        assert error.message == "Something went wrong"
        assert error.code is None
        assert error.category == ErrorCategory.UNKNOWN
        assert error.details == {}

    def test_error_with_code(self):
        """Test creating an OmniError with code."""
        error = OmniError(
            message="Tool not found",
            code=CoreErrorCode.TOOL_NOT_FOUND,
        )
        assert error.code == CoreErrorCode.TOOL_NOT_FOUND
        assert error.category == ErrorCategory.RUNTIME

    def test_error_with_category(self):
        """Test creating an OmniError with category."""
        error = OmniError(
            message="Invalid input",
            code=CoreErrorCode.INVALID_ARGUMENT,
            category=ErrorCategory.VALIDATION,
        )
        assert error.category == ErrorCategory.VALIDATION

    def test_error_with_details(self):
        """Test creating an OmniError with details."""
        details = {"field": "email", "value": "invalid"}
        error = OmniError(
            message="Invalid field",
            code=CoreErrorCode.INVALID_ARGUMENT,
            details=details,
        )
        assert error.details == details

    def test_error_str(self):
        """Test error string representation."""
        error = OmniError(
            message="Not found",
            code=CoreErrorCode.TOOL_NOT_FOUND,
        )
        assert str(error) == "[3001] Not found"

    def test_error_repr(self):
        """Test error repr representation."""
        error = OmniError(
            message="Test error",
            code=CoreErrorCode.INVALID_ARGUMENT,
            category=ErrorCategory.VALIDATION,
            details={"field": "test"},
        )
        repr_str = repr(error)
        assert "Test error" in repr_str
        assert "1001" in repr_str
        assert "VALIDATION" in repr_str

    def test_error_with_code_prefix(self):
        """Test that error message includes code prefix."""
        error = OmniError(
            message="Tool not found",
            code=CoreErrorCode.TOOL_NOT_FOUND,
        )
        # Exception message should include code
        assert "[3001]" in str(error)

    def test_to_dict(self):
        """Test converting error to dictionary."""
        error = OmniError(
            message="Test",
            code=CoreErrorCode.TOOL_NOT_FOUND,
            category=ErrorCategory.RUNTIME,
            details={"key": "value"},
        )
        d = error.to_dict()
        assert d["message"] == "Test"
        assert d["code"] == "3001"
        assert d["category"] == "RUNTIME"
        assert d["details"] == {"key": "value"}


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error(self):
        """Test creating a ValidationError."""
        error = ValidationError(
            message="Invalid email",
            field="email",
            value="not-an-email",
        )
        assert error.code == CoreErrorCode.INVALID_ARGUMENT
        assert error.category == ErrorCategory.VALIDATION
        assert error.details["field"] == "email"
        assert error.details["value"] == "not-an-email"

    def test_validation_error_without_details(self):
        """Test creating a ValidationError without extra details."""
        error = ValidationError(message="Invalid input")
        assert error.details["field"] is None
        assert error.details["value"] is None


class TestSecurityError:
    """Tests for SecurityError exception."""

    def test_security_error(self):
        """Test creating a SecurityError."""
        error = SecurityError(
            message="Malicious pattern detected",
            check_type="mutation_safety",
        )
        assert error.code == CoreErrorCode.SECURITY_CHECK_FAILED
        assert error.category == ErrorCategory.SECURITY
        assert error.details["check_type"] == "mutation_safety"


class TestToolNotFoundError:
    """Tests for ToolNotFoundError exception."""

    def test_tool_not_found_error(self):
        """Test creating a ToolNotFoundError."""
        error = ToolNotFoundError(
            tool_name="git.commit",
            available_tools=["git.status", "git.log"],
        )
        assert error.code == CoreErrorCode.TOOL_NOT_FOUND
        assert error.category == ErrorCategory.RUNTIME
        assert error.message == "Tool not found: git.commit"
        assert error.details["tool"] == "git.commit"
        assert error.details["available_tools"] == ["git.status", "git.log"]

    def test_tool_not_found_error_without_list(self):
        """Test creating a ToolNotFoundError without available tools list."""
        error = ToolNotFoundError(tool_name="unknown.tool")
        assert error.details.get("available_tools") is None


class TestToolExecutionError:
    """Tests for ToolExecutionError exception."""

    def test_tool_execution_error(self):
        """Test creating a ToolExecutionError."""
        error = ToolExecutionError(
            tool_name="git.commit",
            message="Command failed",
            exit_code=1,
            stderr="error: failed",
        )
        assert error.code == CoreErrorCode.TOOL_EXECUTION_FAILED
        assert error.details["tool"] == "git.commit"
        assert error.details["exit_code"] == 1
        assert error.details["stderr"] == "error: failed"


class TestOmniCellError:
    """Tests for OmniCellError exception."""

    def test_omnicell_error(self):
        """Test creating an OmniCellError."""
        error = OmniCellError(
            message="JSON parse failed",
            command="echo test",
            error_type="json_decode",
        )
        assert error.code == CoreErrorCode.CELL_EXECUTION_ERROR
        assert error.details["command"] == "echo test"
        assert error.details["error_type"] == "json_decode"


class TestGetErrorCodeDescription:
    """Tests for get_error_code_description function."""

    def test_valid_descriptions(self):
        """Test getting descriptions for valid error codes."""
        desc = get_error_code_description(CoreErrorCode.TOOL_NOT_FOUND)
        assert desc == "Tool not found"

        desc = get_error_code_description(CoreErrorCode.SECURITY_CHECK_FAILED)
        assert desc == "Security check failed"

    def test_unknown_description(self):
        """Test getting description for unknown error code."""
        desc = get_error_code_description("9999")
        assert desc == "Unknown error"

    def test_all_error_codes_have_descriptions(self):
        """Test that all error codes have descriptions."""
        for code in CoreErrorCode:
            desc = get_error_code_description(code)
            assert desc is not None
            assert len(desc) > 0
