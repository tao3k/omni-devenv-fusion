"""Tests for skill_command decorator with handler integration (v2.2).

Verifies:
- Execution handler params are correctly applied
- Handler config is stored in skill metadata
- ExecutionResult is returned when handler is enabled
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any


class TestSkillCommandHandlerIntegration:
    """Tests for skill_command decorator with Execution Handler (v2.2)."""

    def test_skill_command_with_error_strategy_suppress(self):
        """Test error_strategy='suppress' stores handler config."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_command",
            error_strategy="suppress",
        )
        def test_command() -> dict:
            """Test command with suppressed errors."""
            return {"result": "success"}

        # Verify handler config was stored
        config = test_command._skill_config
        assert config is not None
        assert config["execution"]["handler"] is not None
        assert config["execution"]["handler"]["error_strategy"] == "suppress"

    def test_skill_command_with_log_level_debug(self):
        """Test log_level='debug' stores handler config."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_command",
            log_level="debug",
        )
        def test_command() -> str:
            """Test command with debug logging."""
            return "done"

        config = test_command._skill_config
        assert config["execution"]["handler"] is not None
        assert config["execution"]["handler"]["log_level"] == "debug"
        assert config["execution"]["handler"]["trace_args"] is False

    def test_skill_command_with_trace_args(self):
        """Test trace_args=True stores handler config."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_command",
            trace_args=True,
        )
        def test_command(query: str) -> str:
            """Test command that traces args."""
            return query

        config = test_command._skill_config
        assert config["execution"]["handler"]["trace_args"] is True

    def test_skill_command_combined_handler_params(self):
        """Test multiple handler params are stored correctly."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_command",
            error_strategy="log_only",
            log_level="warning",
            trace_args=True,
            trace_result=False,
            trace_timing=False,
            filter_empty=False,
            max_result_depth=5,
        )
        def test_command() -> dict:
            """Test command with all handler params."""
            return {"key": "value"}

        config = test_command._skill_config
        handler = config["execution"]["handler"]
        assert handler["error_strategy"] == "log_only"
        assert handler["log_level"] == "warning"
        assert handler["trace_args"] is True
        assert handler["trace_result"] is False
        assert handler["trace_timing"] is False
        assert handler["filter_empty"] is False
        assert handler["max_result_depth"] == 5

    def test_skill_command_without_handler_returns_none(self):
        """Test that skill_command without handler params has handler=None."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(name="test_command")
        def test_command() -> str:
            """Test command without handler params."""
            return "done"

        config = test_command._skill_config
        # Without any handler params, handler should be None (not triggered)
        assert config["execution"]["handler"] is None

    def test_skill_command_handler_wraps_function(self):
        """Test that handler wraps the function and output is MCP canonical shape."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_command",
            error_strategy="suppress",
        )
        def test_command() -> dict:
            """Test command that returns result."""
            return {"status": "ok"}

        # Handler + MCP normalization: result is always canonical dict
        result = test_command()
        assert result is not None
        assert isinstance(result, dict)
        assert "content" in result and "isError" in result
        assert result["content"][0]["text"] == '{"status": "ok"}'
        assert result["isError"] is False

    def test_skill_command_handler_with_destructive_hint(self):
        """Test handler works alongside MCP annotations."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="delete_file",
            destructive=True,
            error_strategy="suppress",
            log_level="debug",
        )
        def delete_file(path: str) -> dict:
            """Delete a file."""
            return {"deleted": path}

        config = delete_file._skill_config
        # Verify both annotation and handler are stored
        assert config["annotations"]["destructiveHint"] is True
        assert config["execution"]["handler"]["error_strategy"] == "suppress"
        assert config["execution"]["handler"]["log_level"] == "debug"


class TestExecutionResultFromHandler:
    """Tests verifying ExecutionResult behavior from skill_command with handler."""

    def test_execution_result_ok(self):
        """Test ExecutionResult.ok() factory method."""
        from omni.foundation.api.handlers import ExecutionResult

        result = ExecutionResult.ok(data={"key": "value"}, timing_ms=10.5)
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.timing_ms == 10.5

    def test_execution_result_fail(self):
        """Test ExecutionResult.fail() factory method."""
        from omni.foundation.api.handlers import ExecutionResult

        result = ExecutionResult.fail(error="Something went wrong", error_type="ValueError")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.error_type == "ValueError"

    def test_execution_result_to_dict_success(self):
        """Test ExecutionResult.to_dict() for success case."""
        from omni.foundation.api.handlers import ExecutionResult

        result = ExecutionResult.ok(data={"result": "ok"}, timing_ms=5.0)
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"result": "ok"}
        assert "error" not in d
        assert d["timing_ms"] == 5.0

    def test_execution_result_to_dict_failure(self):
        """Test ExecutionResult.to_dict() for failure case."""
        from omni.foundation.api.handlers import ExecutionResult

        result = ExecutionResult.fail(error="Failed", error_type="RuntimeError", timing_ms=2.0)
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Failed"
        assert d["error_type"] == "RuntimeError"
        assert "data" not in d


class TestErrorStrategy:
    """Tests for ErrorStrategy enum."""

    def test_error_strategy_values(self):
        """Test ErrorStrategy enum values."""
        from omni.foundation.api.handlers import ErrorStrategy

        assert ErrorStrategy.RAISE.value == "raise"
        assert ErrorStrategy.SUPPRESS.value == "suppress"
        assert ErrorStrategy.LOG_ONLY.value == "log_only"

    def test_error_strategy_from_string(self):
        """Test creating ErrorStrategy from string."""
        from omni.foundation.api.handlers import ErrorStrategy

        strategy = ErrorStrategy("suppress")
        assert strategy == ErrorStrategy.SUPPRESS


class TestLoggerConfig:
    """Tests for LoggerConfig dataclass."""

    def test_logger_config_defaults(self):
        """Test LoggerConfig default values."""
        from omni.foundation.api.handlers import LoggerConfig, LogLevel

        config = LoggerConfig()
        assert config.level == LogLevel.INFO
        assert config.trace_args is False
        assert config.trace_result is True
        assert config.trace_timing is True

    def test_logger_config_should_log(self):
        """Test LoggerConfig.should_log() method."""
        from omni.foundation.api.handlers import LoggerConfig, LogLevel

        config = LoggerConfig(level=LogLevel.WARNING)
        assert config.should_log("debug") is False
        assert config.should_log("info") is False
        assert config.should_log("warning") is True
        assert config.should_log("error") is True

    def test_logger_config_off_disables_all(self):
        """Test that OFF level disables all logging."""
        from omni.foundation.api.handlers import LoggerConfig, LogLevel

        config = LoggerConfig(level=LogLevel.OFF)
        assert config.should_log("debug") is False
        assert config.should_log("error") is False


class TestResultConfig:
    """Tests for ResultConfig dataclass."""

    def test_result_config_defaults(self):
        """Test ResultConfig default values."""
        from omni.foundation.api.handlers import ResultConfig

        config = ResultConfig()
        assert config.filter_empty is True
        assert config.max_result_depth == 3
        assert config.include_timing is True
        assert config.include_metadata is True


class TestSkillCommandHandlerDirect:
    """Tests for direct SkillCommandHandler usage."""

    def test_handler_execute_sync_success(self):
        """Test handler executing sync function successfully."""
        from omni.foundation.api.handlers import SkillCommandHandler

        handler = SkillCommandHandler(
            name="test",
            error_strategy=None,  # Use default
        )

        def sample_func() -> str:
            return "success"

        # Handler returns a wrapper, call it to get ExecutionResult
        wrapper = handler(sample_func)
        result = wrapper()
        assert result.success is True
        assert result.data == "success"

    def test_handler_execute_sync_error(self):
        """Test handler with suppressed error."""
        from omni.foundation.api.handlers import SkillCommandHandler, ErrorStrategy

        handler = SkillCommandHandler(
            name="test",
            error_strategy=ErrorStrategy.SUPPRESS,
        )

        def failing_func() -> str:
            raise ValueError("Test error")

        # Handler returns a wrapper, call it to get ExecutionResult
        wrapper = handler(failing_func)
        result = wrapper()
        assert result.success is False
        assert "Test error" in result.error
        assert result.error_type == "ValueError"

    def test_handler_filter_empty_result(self):
        """Test handler filters empty dict/list results."""
        from omni.foundation.api.handlers import SkillCommandHandler

        handler = SkillCommandHandler(
            name="test",
            result_config=None,  # Uses default which filters empty
        )

        def empty_dict_func() -> dict:
            return {}

        wrapper = handler(empty_dict_func)
        result = wrapper()
        assert result.data is None  # Filtered out

        def empty_list_func() -> list:
            return []

        wrapper = handler(empty_list_func)
        result = wrapper()
        assert result.data is None  # Filtered out


class TestCreateHandlerFactory:
    """Tests for create_handler factory function."""

    def test_create_handler_defaults(self):
        """Test create_handler with default values."""
        from omni.foundation.api.handlers import create_handler

        handler = create_handler(name="my_command")
        assert handler.name == "my_command"
        assert handler.error_strategy.value == "raise"

    def test_create_handler_custom_values(self):
        """Test create_handler with custom values."""
        from omni.foundation.api.handlers import create_handler

        handler = create_handler(
            name="custom_handler",
            error_strategy="suppress",
            log_level="debug",
            trace_args=True,
            trace_result=False,
        )
        assert handler.name == "custom_handler"
        assert handler.error_strategy.value == "suppress"
        assert handler.log_config.level.value == "debug"
        assert handler.log_config.trace_args is True
        assert handler.log_config.trace_result is False


# ============================================================================
# Pytest Fixtures for Handler Testing
# ============================================================================


@pytest.fixture
def sample_handler():
    """Create a sample SkillCommandHandler for testing."""
    from omni.foundation.api.handlers import SkillCommandHandler, ErrorStrategy

    return SkillCommandHandler(
        name="sample",
        error_strategy=ErrorStrategy.SUPPRESS,
    )


@pytest.fixture
def sample_decorated_command():
    """Create a sample skill_command with handler for testing."""
    from omni.foundation.api.decorators import skill_command

    @skill_command(
        name="sample_command",
        error_strategy="suppress",
        log_level="debug",
        trace_args=True,
    )
    def sample_command(query: str) -> dict:
        """Sample command for testing."""
        return {"query": query, "processed": True}

    return sample_command


__all__ = [
    "TestSkillCommandHandlerIntegration",
    "TestExecutionResultFromHandler",
    "TestErrorStrategy",
    "TestLoggerConfig",
    "TestResultConfig",
    "TestSkillCommandHandlerDirect",
    "TestCreateHandlerFactory",
    "sample_handler",
    "sample_decorated_command",
]
