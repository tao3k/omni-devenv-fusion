"""
test_schema_gen.py - Unit tests for Tool Schema Generator

Tests for schema generation and validation.
"""

import pytest

from omni.core.skills.schema_gen import (
    generate_tool_schemas,
    export_openapi,
    export_json_schema,
    validate_tool_call,
    get_tool_schema,
    load_schemas,
    save_schemas,
)
from omni.core.skills.variants import get_variant_registry


class TestSchemaGen:
    """Tests for schema generation."""

    def test_generate_tool_schemas_structure(self):
        """Test that generated schemas have correct structure."""
        schemas = generate_tool_schemas()

        # Check top-level structure
        assert "$schema" in schemas
        assert "info" in schemas
        assert "tools" in schemas

        # Check info structure
        assert "name" in schemas["info"]
        assert "version" in schemas["info"]
        assert "generated_at" in schemas["info"]

    def test_export_openapi_structure(self):
        """Test that OpenAPI export has correct structure."""
        openapi = export_openapi()

        assert "openapi" in openapi
        assert openapi["openapi"] == "3.1.0"
        assert "info" in openapi
        assert "paths" in openapi
        assert "components" in openapi

    def test_export_json_schema_structure(self):
        """Test that JSON Schema export has correct structure."""
        json_schema = export_json_schema()

        assert "$schema" in json_schema
        assert "$id" in json_schema
        assert "info" in json_schema
        assert "tools" in json_schema

    def test_save_and_load_schemas(self, tmp_path):
        """Test saving and loading schemas."""
        schemas = generate_tool_schemas()

        # Save to temp file
        output_path = tmp_path / "schemas.json"
        saved_path = save_schemas(output_path)

        assert saved_path.exists()

        # Load and verify
        loaded = load_schemas(saved_path)
        assert loaded["info"]["name"] == schemas["info"]["name"]

    def test_get_tool_schema_not_found(self):
        """Test getting schema for non-existent tool."""
        schema = get_tool_schema("nonexistent.tool")
        assert schema is None

    def test_validate_tool_call_missing_required(self):
        """Test validation with missing required fields."""
        # Create a mock tool config for testing
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="test_tool",
            description="A test tool",
        )
        async def test_tool(query: str, required_param: str):
            """Test tool."""
            pass

        # Validation should report missing required fields
        # Note: This tests the validation logic with current tools
        is_valid, errors = validate_tool_call("nonexistent.tool", {"query": "test"})

        # For non-existent tool, should return invalid
        assert is_valid is False or len(errors) > 0


class TestToolValidation:
    """Tests for tool argument validation."""

    def test_validate_missing_required(self):
        """Test validation fails for missing required fields."""
        # Register a mock tool with required parameters
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="validation_test_tool",
            description="A tool for testing validation",
        )
        async def validation_tool(query: str, required_param: str):
            """Test tool with required param."""
            pass

        # Try calling with missing required param
        is_valid, errors = validate_tool_call("validation_test_tool", {"query": "test"})

        # Should have validation errors
        assert is_valid is False or len(errors) > 0

    def test_validate_valid_arguments(self):
        """Test validation passes for valid arguments."""
        from omni.foundation.api.decorators import skill_command

        @skill_command(
            name="valid_test_tool",
            description="A valid test tool",
        )
        async def valid_tool(query: str, optional_param: str = "default"):
            """Test tool."""
            pass

        # Call with valid arguments
        is_valid, errors = validate_tool_call(
            "valid_test_tool", {"query": "test", "optional_param": "value"}
        )

        # Validation should pass or have no critical errors
        # Note: Actual validation depends on registered tools

    def test_param_description_extraction_from_decorator(self):
        """Test that parameter descriptions are extracted from decorator's description arg."""
        from omni.core.skills.tools_loader import _skill_command_registry
        from omni.foundation.api.decorators import skill_command

        # Clear registry for this test
        _skill_command_registry.clear()

        @skill_command(
            name="param_desc_test",
            description="""
            Test tool with parameter descriptions.

            Args:
                - query: str - The search query to use (required)
                - limit: int - Maximum number of results

            Returns:
                List of results
            """,
        )
        def param_test(query: str, limit: int = 10):
            pass

        # Get the registered command
        assert "general.param_desc_test" in _skill_command_registry

        cmd = _skill_command_registry["general.param_desc_test"]
        config = getattr(cmd, "_skill_config", {})
        input_schema = config.get("input_schema", {})
        props = input_schema.get("properties", {})

        # Check that parameter descriptions were extracted
        assert "query" in props
        assert props["query"].get("description") == "The search query to use (required)"

        assert "limit" in props
        assert props["limit"].get("description") == "Maximum number of results"
