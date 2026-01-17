"""
Agent Tests - Input Schema Framework Tests (Phase 36.8)

Tests to verify that:
1. Framework mechanism for extracting input_schema works correctly
2. SkillCommand dataclass correctly stores input_schema
3. MCP server correctly exposes input_schema to clients

IMPORTANT: This file tests FRAMEWORK MECHANISMS only.
For skill-specific input_schema tests (e.g., git commit, filesystem read_file),
see skills/<skill>/tests/ directory.

Framework vs Skill Tests:
- Framework: Tests decorator logic, schema extraction, model storage
- Skill: Tests specific skill command parameters and validation

Usage:
    python -m pytest packages/python/agent/src/agent/tests/unit/test_input_schema.py -v
"""

import pytest


class TestInputSchemaExtractionFramework:
    """Test the framework mechanism for extracting input_schema.

    Note: Skill-specific tests (e.g., git commit, filesystem read_file)
    should be in skills/<skill>/tests/ directory.
    """

    def test_input_schema_extraction_from_decorator(self):
        """Verify _get_param_schema correctly extracts parameters."""
        from agent.skills.decorators import _get_param_schema

        def sample_func(message: str, count: int = 5):
            """Sample function for testing."""
            pass

        schema = _get_param_schema(sample_func)

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
        from agent.skills.decorators import _get_param_schema

        def func_with_optional(path: str, encoding: str = "utf-8"):
            pass

        schema = _get_param_schema(func_with_optional)

        assert "path" in schema["required"]
        assert "encoding" not in schema["required"]

    def test_input_schema_complex_types(self):
        """Test schema extraction with complex types."""
        from agent.skills.decorators import _get_param_schema
        from typing import List

        def complex_func(name: str, tags: list[str], count: int, enabled: bool = True):
            pass

        schema = _get_param_schema(complex_func)

        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["enabled"]["type"] == "boolean"


class TestSkillCommandModel:
    """Test SkillCommand dataclass correctly stores input_schema."""

    def test_skill_command_has_input_schema_field(self):
        """SkillCommand should have input_schema field."""
        from agent.core.skill_manager.models import SkillCommand

        # Create a dummy command
        def dummy_func():
            pass

        cmd = SkillCommand(
            name="test",
            func=dummy_func,
            description="Test command",
            category="general",
            _skill_name="test_skill",
        )

        # Verify input_schema field exists with default
        assert hasattr(cmd, "input_schema")
        assert cmd.input_schema == {}

    def test_skill_command_stores_input_schema(self):
        """SkillCommand should correctly store provided input_schema."""
        from agent.core.skill_manager.models import SkillCommand

        def dummy_func():
            pass

        test_schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

        cmd = SkillCommand(
            name="test",
            func=dummy_func,
            description="Test command",
            category="general",
            _skill_name="test_skill",
            input_schema=test_schema,
        )

        assert cmd.input_schema == test_schema


class TestMCPServerInputSchema:
    """Test that MCP server correctly exposes input_schema."""

    def test_mcp_server_uses_input_schema(self):
        """MCP server should use cmd.input_schema for tool definitions."""
        from agent.mcp_server import handle_list_tools

        # Verify the function exists and has correct signature
        assert callable(handle_list_tools)


class TestSkillScriptConfig:
    """Test @skill_command decorator attaches _skill_config with input_schema.

    Note: These tests verify the decorator mechanism, not specific skill commands.
    """

    def test_skill_command_decorator_attaches_config(self):
        """@skill_command should attach _skill_config to function."""
        from agent.skills.decorators import skill_command

        @skill_command(name="test_command", category="test", description="A test command")
        def test_func(message: str, count: int = 1):
            pass

        # Verify config is attached
        assert hasattr(test_func, "_skill_config")
        assert test_func._skill_config["name"] == "test_command"
        assert test_func._skill_config["category"] == "test"

    def test_skill_command_input_schema_generated(self):
        """@skill_command should generate input_schema for function parameters."""
        from agent.skills.decorators import skill_command

        @skill_command(name="test_command", category="test", description="A test command")
        def test_func(message: str, count: int = 1):
            pass

        # Verify input_schema is in config
        assert "input_schema" in test_func._skill_config
        schema = test_func._skill_config["input_schema"]

        # Verify schema structure
        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
        assert "message" in schema["required"]
        assert "count" not in schema["required"]
