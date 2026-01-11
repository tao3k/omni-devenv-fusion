"""
Skill Skill Tests - Zero Configuration (Phase 35.1)

Usage:
    def test_templates_command(skill):  # 'skill' fixture auto-injected
        assert hasattr(skill, "templates")

No conftest.py, no complex imports needed!
"""

import ast
import inspect
import pytest
from pathlib import Path

# Use common.skills_path for SSOT path resolution
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

    def test_skill_tools_py_has_valid_syntax(self, skill):
        """skill/tools.py must have valid Python syntax."""
        tools_path = SKILLS_DIR("skill") / "tools.py"
        assert tools_path.exists(), f"skill/tools.py not found: {tools_path}"

        is_valid, error = validate_python_syntax(tools_path)
        assert is_valid, f"skill/tools.py has syntax error: {error}"

    def test_skill_scripts_have_valid_syntax(self, skill):
        """All skill/scripts/*.py files must have valid Python syntax."""
        scripts_dir = SKILLS_DIR("skill") / "scripts"
        if not scripts_dir.exists():
            return  # Skip if no scripts directory

        invalid_files = []
        for py_file in scripts_dir.glob("*.py"):
            is_valid, error = validate_python_syntax(py_file)
            if not is_valid:
                invalid_files.append(f"scripts/{py_file.name}: {error}")

        assert len(invalid_files) == 0, (
            f"Found {len(invalid_files)} files with syntax errors:\n" + "\n".join(invalid_files)
        )

    def test_core_task_py_has_valid_syntax(self, skill):
        """Core task.py must have valid Python syntax (critical path)."""
        # Find task.py using SSOT project root
        from common.gitops import get_project_root

        project_root = get_project_root()
        task_path = project_root / "packages/python/agent/src/agent/skills/core/task.py"
        assert task_path.exists(), f"task.py not found: {task_path}"

        is_valid, error = validate_python_syntax(task_path)
        assert is_valid, f"task.py has syntax error: {error}"


class TestSkillTemplatesCommand:
    """Test skill.templates command functionality."""

    def test_templates_command_exists(self, skill):
        """The templates command should exist in skill tools."""
        assert hasattr(skill, "templates"), "skill module missing 'templates' function"

    def test_templates_list_git(self, skill):
        """skill.templates with skill_name='git' and action='list' should work."""
        result = skill.templates(skill_name="git", action="list")

        # Handle CommandResult wrapper
        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str), "templates() should return string"
        assert "git" in result.lower(), "Result should mention 'git'"
        assert "Templates" in result or "templates" in result, "Result should mention templates"

    def test_templates_list_filesystem(self, skill):
        """skill.templates with skill_name='filesystem' should work."""
        result = skill.templates(skill_name="filesystem", action="list")

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str), "templates() should return string"

    def test_templates_invalid_action(self, skill):
        """skill.templates with invalid action should return error."""
        result = skill.templates(skill_name="git", action="invalid_action")

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str), "templates() should return string"
        assert "Unknown action" in result or "error" in result.lower(), (
            "Should indicate invalid action"
        )

    def test_templates_nonexistent_skill(self, skill):
        """skill.templates with nonexistent skill should return error."""
        result = skill.templates(skill_name="nonexistent_skill_xyz", action="list")

        if hasattr(result, "data"):
            result = result.data if result.success else result.error

        assert isinstance(result, str), "templates() should return string"
        assert "no templates" in result.lower() or "not found" in result.lower()


class TestSkillCommandsMetadata:
    """Test skill commands have proper metadata."""

    def test_commands_have_skill_command_metadata(self, skill):
        """All skill commands should have @skill_command metadata."""
        for name, func in inspect.getmembers(skill, inspect.isfunction):
            if hasattr(func, "_is_skill_command"):
                assert hasattr(func, "_skill_config")
                config = func._skill_config
                assert "name" in config
                assert "category" in config

    def test_tools_py_has_commands(self, skill):
        """skill/tools.py should have @skill_command decorated functions."""
        commands = [
            name
            for name, func in inspect.getmembers(skill, inspect.isfunction)
            if hasattr(func, "_is_skill_command")
        ]
        assert len(commands) > 0, "No skill commands found"
        assert "templates" in commands
        assert "discover" in commands
        assert "suggest" in commands
