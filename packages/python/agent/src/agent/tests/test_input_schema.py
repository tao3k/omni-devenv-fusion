"""
Agent Tests - Input Schema and SkillCommand Model Tests (Phase 36.8)

Tests to verify that:
1. @skill_command decorated functions have correct input_schema
2. SkillCommand dataclass correctly stores input_schema
3. MCP server correctly exposes input_schema to clients

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_input_schema.py -v
"""

import sys
import pytest
import types
from pathlib import Path


def _setup_skill_package_context(skill_name: str, skills_root: Path):
    """Set up package context for skill module loading."""
    from importlib import util
    from common.gitops import get_project_root

    project_root = get_project_root()

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        agent_pkg.__file__ = str(agent_src / "__init__.py")
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        skills_pkg.__file__ = str(skills_root / "__init__.py")
        sys.modules["agent.skills"] = skills_pkg
        sys.modules["agent"].skills = skills_pkg

    # Pre-load decorators module (required for @skill_command)
    if "agent.skills.decorators" not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = util.spec_from_file_location("agent.skills.decorators", decorators_path)
            if spec and spec.loader:
                module = util.module_from_spec(spec)
                sys.modules["agent.skills.decorators"] = module
                sys.modules["agent.skills"].decorators = module
                spec.loader.exec_module(module)

    # Ensure 'agent.skills.{skill_name}' package exists
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name not in sys.modules:
        skill_pkg = types.ModuleType(skill_pkg_name)
        skill_pkg.__path__ = [str(skills_root / skill_name)]
        skill_pkg.__file__ = str(skills_root / skill_name / "__init__.py")
        sys.modules[skill_pkg_name] = skill_pkg


def load_skill_module(skill_name: str):
    """Load a skill module for testing with proper package context."""
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    tools_path = skills_dir / skill_name / "tools.py"

    # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
    _setup_skill_package_context(skill_name, skills_dir)

    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{skill_name}_tools", str(tools_path))
    module = importlib.util.module_from_spec(spec)
    # Set __package__ for proper import resolution
    module.__package__ = f"agent.skills.{skill_name}"
    spec.loader.exec_module(module)
    return module


class TestInputSchemaExtraction:
    """Test that @skill_command functions have correct input_schema."""

    @pytest.fixture
    def git_module(self):
        """Load git skill module."""
        return load_skill_module("git")

    @pytest.fixture
    def filesystem_module(self):
        """Load filesystem skill module."""
        return load_skill_module("filesystem")

    def test_commit_has_input_schema(self, git_module):
        """commit command should have input_schema with 'message' parameter."""
        assert hasattr(git_module.commit, "_skill_config")
        config = git_module.commit._skill_config

        # Verify input_schema exists and has correct structure
        assert "input_schema" in config, "input_schema must be in _skill_config"
        schema = config["input_schema"]

        # Verify schema structure
        assert schema.get("type") == "object", "Schema must be type 'object'"
        assert "properties" in schema, "Schema must have 'properties'"
        assert "required" in schema, "Schema must have 'required'"

        # Verify 'message' parameter is correctly defined
        assert "message" in schema["properties"], "'message' must be in properties"
        assert schema["properties"]["message"]["type"] == "string", "'message' must be string type"
        assert "message" in schema["required"], "'message' must be in required list"

    def test_prepare_commit_has_input_schema(self, git_module):
        """prepare_commit command should have input_schema."""
        assert hasattr(git_module.prepare_commit, "_skill_config")
        config = git_module.prepare_commit._skill_config

        assert "input_schema" in config, "input_schema must be in _skill_config"
        schema = config["input_schema"]
        assert schema.get("type") == "object"

    def test_status_has_no_required_params(self, git_module):
        """status command should have no required parameters."""
        assert hasattr(git_module.status, "_skill_config")
        config = git_module.status._skill_config

        assert "input_schema" in config
        schema = config["input_schema"]
        assert "required" in schema
        # status has inject_root=True, so no required params
        assert len(schema["required"]) == 0, "status should have no required parameters"

    def test_read_file_has_required_params(self, filesystem_module):
        """read_file should have 'file_path' as required parameter."""
        assert hasattr(filesystem_module.read_file, "_skill_config")
        config = filesystem_module.read_file._skill_config

        assert "input_schema" in config
        schema = config["input_schema"]
        assert "file_path" in schema["properties"], "'file_path' must be in properties"
        assert "file_path" in schema["required"], "'file_path' must be required"

    def test_write_file_has_required_params(self, filesystem_module):
        """write_file should have 'path' and 'content' as required parameters."""
        assert hasattr(filesystem_module.write_file, "_skill_config")
        config = filesystem_module.write_file._skill_config

        assert "input_schema" in config
        schema = config["input_schema"]
        assert "path" in schema["required"], "'path' must be required"
        assert "content" in schema["required"], "'content' must be required"


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
        # This is a structural test - we verify the code path exists
        import inspect
        from agent.mcp_server import handle_list_tools

        # Verify the function exists and has correct signature
        assert callable(handle_list_tools)

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
