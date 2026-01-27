"""
test_validation_guard.py - Unit Tests for ResilientReAct Components

Tests for:
- ArgumentValidator: Schema-based parameter validation
- OutputCompressor: Long output compression
- EpistemicGater: Task intent verification
- ResilientReAct: Workflow execution with validation
"""

import pytest

from omni.agent.core.omni.react import (
    ArgumentValidator,
    OutputCompressor,
    ValidationResult,
    ResilientReAct,
)
from omni.agent.core.omni.loop import EpistemicGater


class TestValidationResult:
    """Tests for ValidationResult Pydantic model."""

    def test_valid_result(self):
        """Should create valid ValidationResult."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.error_message is None
        assert result.cleaned_args is None

    def test_invalid_result_with_error(self):
        """Should create invalid ValidationResult with error message."""
        result = ValidationResult(is_valid=False, error_message="Missing required argument: path")
        assert result.is_valid is False
        assert result.error_message == "Missing required argument: path"

    def test_result_with_cleaned_args(self):
        """Should include cleaned arguments."""
        result = ValidationResult(is_valid=True, cleaned_args={"path": "/test/file.txt"})
        assert result.cleaned_args == {"path": "/test/file.txt"}


class TestOutputCompressor:
    """Tests for OutputCompressor."""

    def test_short_output_unchanged(self):
        """Should not compress short output."""
        result = OutputCompressor.compress("short result", max_len=2000)
        assert result == "short result"

    def test_empty_output_unchanged(self):
        """Should return empty string unchanged."""
        result = OutputCompressor.compress("", max_len=2000)
        assert result == ""

    def test_long_output_compressed(self):
        """Should compress long output."""
        long_text = "x" * 5000
        result = OutputCompressor.compress(long_text, max_len=2000)

        assert len(result) < len(long_text)
        assert "[Output Truncated" in result
        assert "Hint: Use a specific tool" in result

    def test_default_max_len(self):
        """Should use default max_len of 2000."""
        text_1999 = "a" * 1999
        result = OutputCompressor.compress(text_1999)
        assert result == text_1999

        text_2001 = "b" * 2001
        result = OutputCompressor.compress(text_2001)
        assert "[Output Truncated" in result


class TestArgumentValidator:
    """Tests for ArgumentValidator."""

    def test_no_schema(self):
        """Should pass through when no schema provided."""
        result = ArgumentValidator.validate(None, {"path": "/test"})
        assert result.is_valid is True
        assert result.cleaned_args == {"path": "/test"}

    def test_no_parameters_in_schema(self):
        """Should pass through when schema has no parameters."""
        result = ArgumentValidator.validate({}, {"path": "/test"})
        assert result.is_valid is True

    def test_missing_required_field(self):
        """Should detect missing required fields."""
        schema = {
            "parameters": {
                "required": ["path", "content"],
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            }
        }
        result = ArgumentValidator.validate(schema, {"path": "/test"})
        assert result.is_valid is False
        assert "content" in result.error_message

    def test_all_required_fields_present(self):
        """Should pass when all required fields present."""
        schema = {"parameters": {"required": ["path"], "properties": {"path": {"type": "string"}}}}
        result = ArgumentValidator.validate(schema, {"path": "/test/file.txt"})
        assert result.is_valid is True
        assert result.cleaned_args == {"path": "/test/file.txt"}

    def test_string_to_integer_conversion(self):
        """Should convert string to integer when expected."""
        schema = {
            "parameters": {"required": ["lines"], "properties": {"lines": {"type": "integer"}}}
        }
        result = ArgumentValidator.validate(schema, {"lines": "42"})
        assert result.is_valid is True
        assert result.cleaned_args["lines"] == 42

    def test_invalid_integer_string(self):
        """Should fail when string cannot be converted to integer."""
        schema = {
            "parameters": {"required": ["lines"], "properties": {"lines": {"type": "integer"}}}
        }
        result = ArgumentValidator.validate(schema, {"lines": "not-a-number"})
        assert result.is_valid is False
        assert "must be an integer" in result.error_message

    def test_extra_fields_allowed(self):
        """Should pass when extra fields are provided."""
        schema = {"parameters": {"required": ["path"], "properties": {"path": {"type": "string"}}}}
        result = ArgumentValidator.validate(schema, {"path": "/test", "extra": "value"})
        assert result.is_valid is True


class TestEpistemicGater:
    """Tests for EpistemicGater."""

    def setup_method(self):
        self.gater = EpistemicGater()

    def test_empty_task_rejected(self):
        """Should reject empty task."""
        should_proceed, reason, metadata = self.gater.evaluate("")
        assert should_proceed is False

    def test_very_short_task_rejected(self):
        """Should reject very short task."""
        should_proceed, reason, metadata = self.gater.evaluate("hi")
        assert should_proceed is False

    def test_vague_task_rejected(self):
        """Should reject vague tasks like 'do something'."""
        should_proceed, reason, metadata = self.gater.evaluate("do something")
        assert should_proceed is False
        assert "vague" in reason.lower()

    def test_fix_it_rejected(self):
        """Should reject 'fix it' task."""
        should_proceed, reason, metadata = self.gater.evaluate("fix it")
        assert should_proceed is False

    def test_help_me_rejected(self):
        """Should reject 'help me' task."""
        should_proceed, reason, metadata = self.gater.evaluate("help me")
        assert should_proceed is False

    def test_valid_specific_task(self):
        """Should accept specific tasks."""
        should_proceed, reason, metadata = self.gater.evaluate("Read the file /path/to/config.json")
        assert should_proceed is True

    def test_info_seeking_allowed(self):
        """Should allow information seeking questions."""
        should_proceed, reason, metadata = self.gater.evaluate("What is Python?")
        assert should_proceed is True
        assert metadata.get("task_type") == "info_seeking"

    def test_explain_allowed(self):
        """Should allow explanation requests."""
        should_proceed, reason, metadata = self.gater.evaluate("Explain how async/await works")
        assert should_proceed is True

    def test_context_warning_for_file(self):
        """Should add warning when file mentioned without path."""
        should_proceed, reason, metadata = self.gater.evaluate("Read the file and check for errors")
        assert should_proceed is True
        assert "context_warning" in metadata


class TestResilientReActWorkflow:
    """Tests for ResilientReAct workflow execution."""

    def test_compute_tool_hash(self):
        """Should compute consistent hash for tool calls."""
        from unittest.mock import MagicMock

        mock_engine = MagicMock()
        workflow = ResilientReAct(
            engine=mock_engine,
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        hash1 = workflow._compute_tool_hash("read_file", {"path": "/test"})
        hash2 = workflow._compute_tool_hash("read_file", {"path": "/test"})
        hash3 = workflow._compute_tool_hash("read_file", {"path": "/other"})

        assert hash1 == hash2
        assert hash1 != hash3

    def test_clean_artifacts(self):
        """Should clean thinking blocks and tool call artifacts."""
        from unittest.mock import MagicMock

        workflow = ResilientReAct(
            engine=MagicMock(),
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        dirty = "<thinking>I am thinking</thinking>Some content[TOOL_CALL: test]()[/TOOL_CALL]"
        clean = workflow._clean_artifacts(dirty)

        assert "<thinking>" not in clean
        assert "[TOOL_CALL:" not in clean
        assert "[/TOOL_CALL]" not in clean
        assert "Some content" in clean

    def test_check_completion_exit_loop_now(self):
        """Should detect EXIT_LOOP_NOW signal."""
        from unittest.mock import MagicMock

        workflow = ResilientReAct(
            engine=MagicMock(),
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        assert workflow._check_completion("Task done. EXIT_LOOP_NOW") is True
        assert workflow._check_completion("Task done") is False

    def test_check_completion_task_completed(self):
        """Should detect TASK_COMPLETED_SUCCESSFULLY signal."""
        from unittest.mock import MagicMock

        workflow = ResilientReAct(
            engine=MagicMock(),
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        assert workflow._check_completion("TASK_COMPLETED_SUCCESSFULLY") is True

    def test_format_result(self):
        """Should format results correctly."""
        from unittest.mock import MagicMock

        workflow = ResilientReAct(
            engine=MagicMock(),
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        error_result = workflow._format_result("read_file", "Error: not found", True)
        assert "Error" in error_result
        assert "read_file" in error_result

        success_result = workflow._format_result("read_file", "file content", False)
        assert "Result" in success_result
        assert "read_file" in success_result

    def test_get_stats(self):
        """Should return workflow statistics."""
        from unittest.mock import MagicMock

        mock_engine = MagicMock()
        workflow = ResilientReAct(
            engine=mock_engine,
            get_tool_schemas=lambda: [],
            execute_tool=lambda n, a: "",
        )

        # Manually set some state
        workflow.step_count = 5
        workflow.tool_calls_count = 10
        workflow._tool_hash_history.add("hash1")
        workflow._tool_hash_history.add("hash2")

        stats = workflow.get_stats()

        assert stats["step_count"] == 5
        assert stats["tool_calls_count"] == 10
        assert stats["unique_tool_calls"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
