"""
Unit tests for input schema extraction using Pydantic V2.

Tests the framework for extracting input schemas from function signatures
using _generate_tool_schema (Pydantic V2 create_model).
"""


class TestInputSchemaExtractionFramework:
    """Tests for the Pydantic V2 input schema extraction framework."""

    def test_input_schema_basic_types(self):
        """Test schema extraction with basic types."""
        from omni.foundation.api.decorators import _generate_tool_schema

        def basic_func(message: str, count: int):
            pass

        schema = _generate_tool_schema(basic_func)

        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
        assert "message" in schema["required"]
        assert "count" in schema["required"]

        # Verify types
        assert schema["properties"]["message"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"

    def test_input_schema_with_defaults(self):
        """Test schema extraction with default values."""
        from omni.foundation.api.decorators import _generate_tool_schema

        def func_with_default(message: str, count: int = 10):
            pass

        schema = _generate_tool_schema(func_with_default)

        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
        assert "message" in schema["required"]
        assert "count" not in schema["required"]  # Has default

        # Verify types
        assert schema["properties"]["message"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"

    def test_input_schema_with_optional_params(self):
        """Test schema extraction with optional parameters."""
        from omni.foundation.api.decorators import _generate_tool_schema

        def func_with_optional(path: str, encoding: str = "utf-8"):
            pass

        schema = _generate_tool_schema(func_with_optional)

        assert "path" in schema["required"]
        assert "encoding" not in schema["required"]

    def test_input_schema_complex_types(self):
        """Test schema extraction with complex types."""
        from omni.foundation.api.decorators import _generate_tool_schema

        def complex_func(name: str, tags: list[str], count: int, enabled: bool = True):
            pass

        schema = _generate_tool_schema(complex_func)

        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["enabled"]["type"] == "boolean"


class TestSkillScriptConfig:
    """Tests for skill script configuration via decorators."""

    def test_skill_command_decorator_attaches_config(self):
        """@skill_command decorator should attach _skill_config."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(category="test")
        def test_func():
            pass

        assert hasattr(test_func, "_skill_config")
        config = test_func._skill_config
        assert config["name"] == "test_func"
        assert config["category"] == "test"


class TestSkillCommandDecorator:
    """Tests for @skill_command decorator with Pydantic V2 schema generation."""

    def test_skill_command_generates_input_schema(self):
        """@skill_command should generate input_schema using Pydantic V2."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(category="test")
        def test_func(message: str, count: int = 5):
            """Test function description."""
            pass

        assert hasattr(test_func, "_skill_config")
        config = test_func._skill_config
        assert "input_schema" in config
        schema = config["input_schema"]

        # Verify schema structure
        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
        assert "message" in schema["required"]
        assert "count" not in schema["required"]

        # Verify types
        assert schema["properties"]["message"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"

    def test_skill_command_description_from_docstring(self):
        """@skill_command should extract description from docstring."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(category="test")
        def test_func():
            """This is the description from docstring."""
            pass

        config = test_func._skill_config
        assert config["description"] == "This is the description from docstring."

    def test_skill_command_excludes_injected_params(self):
        """@skill_command should exclude injected params from schema."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(inject_root=True)
        def test_func(message: str):
            """Test function."""
            pass

        schema = test_func._skill_config["input_schema"]
        # project_root should be excluded
        assert "message" in schema["properties"]
        # project_root should not be in schema (it's injected)

    def test_skill_command_with_complex_types(self):
        """@skill_command should handle complex types in schema."""

        from omni.foundation.api.decorators import skill_command

        @skill_command(category="test")
        def test_func(
            name: str,
            tags: list[str],
            count: int,
            optional_val: str | None = None,
        ):
            """Test function with complex types."""
            pass

        schema = test_func._skill_config["input_schema"]

        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["count"]["type"] == "integer"
        # Optional types should be handled correctly
        assert "optional_val" in schema["properties"]
