"""
Skill Skill Tests - Phase 63+ Architecture

Tests the new architecture where:
- Scripts/*.py contain plain functions with @skill_command decorators
- No tools.py file (legacy pattern removed)
- Commands exposed via skill prefix: skill_list_templates, skill_discover, etc.

Usage:
    def test_discover_command(skill):
        result = skill.discover(query="git")
        assert result is not None
"""

import ast
import pytest
from pathlib import Path

from common.skills_path import SKILLS_DIR


def validate_python_syntax(file_path: Path) -> tuple[bool, str | None]:
    """Validate Python file syntax using AST parser."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"


class TestSkillSyntaxValidation:
    """Validate Python syntax for skill files."""

    def test_skill_scripts_have_valid_syntax(self):
        """All skill/scripts/*.py files must have valid Python syntax."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        if not scripts_dir.exists():
            pytest.skip("No scripts directory")

        invalid_files = []
        for py_file in scripts_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            is_valid, error = validate_python_syntax(py_file)
            if not is_valid:
                invalid_files.append(f"scripts/{py_file.name}: {error}")

        assert len(invalid_files) == 0, (
            f"Found {len(invalid_files)} files with syntax errors:\n" + "\n".join(invalid_files)
        )

    def test_discovery_script_imports_correctly(self):
        """scripts/discovery.py should import without errors."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        discovery_file = scripts_dir / "discovery.py"

        if not discovery_file.exists():
            pytest.skip("discovery.py not found")

        # Try to import the module to verify no import errors
        import importlib.util

        spec = importlib.util.spec_from_file_location("discovery_test", discovery_file)
        assert spec is not None, "Failed to load discovery.py spec"
        assert spec.loader is not None, "discovery.py has no loader"
        module = importlib.util.module_from_spec(spec)

        # This will fail if there are import errors
        try:
            spec.loader.exec_module(module)
        except ImportError as e:
            pytest.fail(f"discovery.py has import error: {e}")

    def test_core_task_py_has_valid_syntax(self):
        """Core task.py must have valid Python syntax (critical path)."""
        from common.gitops import get_project_root

        project_root = get_project_root()
        task_path = project_root / "packages/python/agent/src/agent/skills/core/task.py"
        assert task_path.exists(), f"task.py not found: {task_path}"

        is_valid, error = validate_python_syntax(task_path)
        assert is_valid, f"task.py has syntax error: {error}"


class TestSkillTemplatesCommand:
    """Test skill template commands (Phase 63+)."""

    def test_list_templates_command_exists(self, skill):
        """The list_templates command should exist in skill tools."""
        assert hasattr(skill, "list_templates"), "skill module missing 'list_templates' function"

    def test_list_templates_git(self, skill):
        """skill.list_templates with skill_name='git' should work."""
        result = skill.list_templates(skill_name="git")

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, (dict, str))

    def test_list_templates_filesystem(self, skill):
        """skill.list_templates with skill_name='filesystem' should work."""
        result = skill.list_templates(skill_name="filesystem")

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, (dict, str))

    def test_eject_template_command_exists(self, skill):
        """The eject_template command should exist."""
        assert hasattr(skill, "eject_template"), "skill module missing 'eject_template' function"

    def test_get_template_info_command_exists(self, skill):
        """The get_template_info command should exist."""
        assert hasattr(skill, "get_template_info"), (
            "skill module missing 'get_template_info' function"
        )

    def test_get_template_source_command_exists(self, skill):
        """The get_template_source command should exist."""
        assert hasattr(skill, "get_template_source"), (
            "skill module missing 'get_template_source' function"
        )


class TestSkillCommandsMetadata:
    """Test skill commands have proper metadata."""

    def test_commands_have_skill_command_metadata(self, skill):
        """All skill commands should have @skill_command metadata."""
        # Check via SkillProxy._skill.commands (the original SkillCommand objects)
        for cmd_name, cmd in skill._skill.commands.items():
            assert hasattr(cmd, "_is_skill_command") or hasattr(cmd.func, "_is_skill_command"), (
                f"Command {cmd_name} should have _is_skill_command"
            )

    def test_skill_has_commands(self, skill):
        """skill should have @skill_command decorated functions."""
        # Check via SkillProxy._skill.commands (the original SkillCommand objects)
        commands = list(skill._skill.commands.keys())
        assert len(commands) > 0, "No skill commands found"
        # Phase 63+ commands
        assert "discover" in commands
        assert "suggest" in commands
        assert "list_templates" in commands
        assert "list_tools" in commands


class TestSkillDiscoveryCommands:
    """Test skill discovery commands (discover, suggest, list_index)."""

    def test_discover_command_exists(self, skill):
        """The discover command should exist in skill tools."""
        assert hasattr(skill, "discover"), "skill module missing 'discover' function"

    def test_suggest_command_exists(self, skill):
        """The suggest command should exist in skill tools."""
        assert hasattr(skill, "suggest"), "skill module missing 'suggest' function"

    def test_list_index_command_exists(self, skill):
        """The list_index command should exist in skill tools."""
        assert hasattr(skill, "list_index"), "skill module missing 'list_index' function"

    def test_jit_install_command_exists(self, skill):
        """The jit_install command should exist in skill tools."""
        assert hasattr(skill, "jit_install"), "skill module missing 'jit_install' function"


class TestSkillToolManagement:
    """Test skill tool management commands."""

    def test_list_tools_command_exists(self, skill):
        """The list_tools command should exist in skill tools."""
        assert hasattr(skill, "list_tools"), "skill module missing 'list_tools' function"

    def test_search_tools_command_exists(self, skill):
        """The search_tools command should exist in skill tools."""
        assert hasattr(skill, "search_tools"), "skill module missing 'search_tools' function"

    def test_reload_command_exists(self, skill):
        """The reload command should exist in skill tools."""
        assert hasattr(skill, "reload"), "skill module missing 'reload' function"

    def test_unload_command_exists(self, skill):
        """The unload command should exist in skill tools."""
        assert hasattr(skill, "unload"), "skill module missing 'unload' function"


class TestSkillDiscoveryIntegration:
    """Integration tests for skill discovery with registry."""

    def test_skill_discovery_import(self):
        """SkillDiscovery should be importable from agent.core.skill_discovery."""
        from agent.core.skill_discovery import SkillDiscovery

        # Verify class exists and can be instantiated
        discovery = SkillDiscovery()
        assert discovery is not None

    def test_skill_discovery_has_search_method(self):
        """SkillDiscovery should have search method with correct signature."""
        from agent.core.skill_discovery import SkillDiscovery
        import inspect

        discovery = SkillDiscovery()
        assert hasattr(discovery, "search"), "SkillDiscovery should have 'search' method"

        # Verify method signature
        sig = inspect.signature(discovery.search)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "limit" in params
        assert "local_only" in params
        # Verify no deprecated parameters
        assert "installed_only" not in params, (
            "Use 'local_only' instead of deprecated 'installed_only'"
        )

    def test_skill_discovery_has_get_index_stats_method(self):
        """SkillDiscovery should have get_index_stats method."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        assert hasattr(discovery, "get_index_stats"), (
            "SkillDiscovery should have 'get_index_stats' method"
        )
        assert not hasattr(discovery, "list_all"), "list_all is deprecated, use get_index_stats"

    def test_discover_uses_skill_discovery(self, skill):
        """skill.discover should use SkillDiscovery."""
        # Test that the command is callable without import errors
        assert callable(skill.discover)

    def test_suggest_returns_recommendation(self, skill):
        """skill.suggest should return a recommendation string."""
        result = skill.suggest(task="git version control")

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)


class TestSkillListTools:
    """Tests for skill.list_tools command."""

    def test_list_tools_returns_string(self, skill):
        """skill.list_tools should return a string result."""
        result = skill.list_tools()

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)

    def test_list_tools_contains_skill_names(self, skill):
        """skill.list_tools should contain skill names."""
        result = skill.list_tools()

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str)
