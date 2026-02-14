"""
Unit tests for @skill_command decorator and script-based loading.

Tests the new metadata-driven architecture where scripts/*.py
can be loaded directly without tools.py router layer.

Updated for ODF-EP v6.0 (Pydantic V2):
- Config structure uses nested "execution" dict
"""

import pytest

from omni.foundation.api.decorators import (
    CommandResult,
    get_script_config,
    is_skill_command,
    skill_command,
)


class TestSkillScriptDecorator:
    """Tests for @skill_command decorator."""

    def test_skill_command_marks_function(self) -> None:
        """Verify @skill_command marks function with marker."""

        @skill_command(description="Test command")
        def test_command(arg1: str) -> str:
            """A test command."""
            return f"Result: {arg1}"

        assert is_skill_command(test_command) is True

    def test_skill_command_stores_config(self) -> None:
        """Verify @skill_command stores config correctly."""

        @skill_command(
            name="custom_name",
            description="A custom command",
            category="write",
            inject_root=True,
        )
        def my_func(arg1: str) -> str:
            """My function docstring."""
            return arg1

        config = get_script_config(my_func)
        assert config is not None
        assert config["name"] == "custom_name"
        assert config["description"] == "A custom command"
        assert config["category"] == "write"
        # New structure: execution config is nested
        assert config["execution"]["inject_root"] is True

    def test_skill_command_defaults(self) -> None:
        """Verify @skill_command has correct defaults."""

        @skill_command()
        def default_func() -> str:
            """A function."""
            return "ok"

        config = get_script_config(default_func)
        assert config is not None
        assert config["name"] == "default_func"
        assert config["category"] == "general"
        # New structure: execution config is nested
        assert config["execution"]["inject_root"] is False
        assert config["execution"]["max_attempts"] == 1

    def test_skill_command_generates_input_schema(self) -> None:
        """Verify @skill_command generates input schema from type hints."""

        @skill_command(description="Test")
        def typed_func(name: str, count: int = 5) -> str:
            """A typed function."""
            return f"{name}: {count}"

        config = get_script_config(typed_func)
        assert config is not None
        schema = config["input_schema"]
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "count" in schema["properties"]
        assert "name" in schema["required"]

    def test_skill_command_description_from_docstring(self) -> None:
        """Verify @skill_command uses docstring if no description."""

        @skill_command()
        def with_docstring() -> str:
            """This is the description from docstring."""
            return "ok"

        config = get_script_config(with_docstring)
        assert config is not None
        assert config["description"] == "This is the description from docstring."

    def test_skill_command_cache_ttl(self) -> None:
        """Verify @skill_command stores cache_ttl in execution config."""

        @skill_command(
            description="Cached command",
            cache_ttl=60.0,
        )
        def cached_func() -> str:
            """A cached function."""
            return "result"

        config = get_script_config(cached_func)
        assert config is not None
        assert config["execution"]["cache_ttl"] == 60.0

    def test_skill_command_cache_defaults(self) -> None:
        """Verify @skill_command has correct caching defaults."""

        @skill_command()
        def uncached_func() -> str:
            """A function without caching."""
            return "result"

        config = get_script_config(uncached_func)
        assert config["execution"]["cache_ttl"] == 0.0

    def test_skill_command_inject_settings(self) -> None:
        """Verify @skill_command stores inject_settings."""

        @skill_command(
            description="Test",
            inject_settings=["api_key", "model"],
        )
        def api_func() -> str:
            """API function."""
            return "result"

        config = get_script_config(api_func)
        assert config is not None
        assert config["execution"]["inject_settings"] == ["api_key", "model"]


class TestSkillCommandDecorator:
    """Tests for existing @skill_command (ensure backward compatibility)."""

    def test_skill_command_still_works(self) -> None:
        """Verify @skill_command continues to work."""

        @skill_command(description="Test", category="test")
        def test_cmd() -> str:
            """A test command."""
            return "ok"

        assert hasattr(test_cmd, "_is_skill_command")
        assert hasattr(test_cmd, "_skill_config")

    def test_skill_command_returns_direct_result(self) -> None:
        """Verify @skill_command returns MCP canonical result (content[].text)."""

        @skill_command()
        def simple() -> str:
            """Simple function."""
            return "result"

        # Decorator normalizes return to MCP tools/call result shape
        result = simple()
        assert isinstance(result, dict)
        assert result.get("content") and result["content"][0].get("text") == "result"
        assert result.get("isError") is False
        assert not isinstance(result, CommandResult)


class TestCommandResultGeneric:
    """Tests for CommandResult Generic[T] type."""

    def test_command_result_typed_dict(self) -> None:
        """Verify CommandResult[dict] preserves type."""
        result = CommandResult(success=True, data={"key": "value"})
        assert isinstance(result.data, dict)
        assert result.data["key"] == "value"

    def test_command_result_typed_str(self) -> None:
        """Verify CommandResult[str] preserves type."""
        result = CommandResult(success=True, data="hello")
        assert isinstance(result.data, str)
        assert result.data == "hello"

    def test_command_result_computed_fields(self) -> None:
        """Verify @computed_field is included in model_dump()."""
        result = CommandResult(
            success=False,
            data={},
            error="connection refused",
            metadata={"retry_count": 2, "duration_ms": 150.0},
        )

        # Computed fields should be accessible
        assert result.is_retryable is True
        assert result.retry_count == 2
        assert result.duration_ms == 150.0

        # Computed fields should be in serialization
        serialized = result.model_dump()
        assert "is_retryable" in serialized
        assert "retry_count" in serialized
        assert "duration_ms" in serialized

    def test_command_result_frozen(self) -> None:
        """Verify CommandResult is frozen (immutable)."""
        result = CommandResult(success=True, data="test")
        with pytest.raises(Exception):
            result.success = False


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
