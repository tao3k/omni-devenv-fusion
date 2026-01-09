"""
Template Skill Tests - Zero Configuration (Phase 35.1)

This file demonstrates how to write tests for YOUR skill.

Copy this file to your skill's tests/ directory and update:
1. Rename 'test_template_commands.py' to 'test_my_skill_commands.py'
2. Replace 'template' with your skill name (e.g., 'my_skill')
3. Update tests to match your commands

For the _template itself, we test using the 'skill' fixture (skill management skill).

Run Tests:
    uv run pytest assets/skills/_template/tests/ -v
    uv run pytest assets/skills/ -v
    omni skill test _template
"""

import pytest
import inspect

# SSOT: Use common.skills_path for path resolution
from common.skills_path import SKILLS_DIR


# =============================================================================
# For your skill: Copy and customize these patterns
# =============================================================================

"""
Example: Testing your own skill

my_skill/tests/test_my_skill_commands.py:

def test_my_command_exists(my_skill):  # 'my_skill' fixture auto-injected
    assert hasattr(my_skill, "my_command")
    assert callable(my_skill.my_command)


def test_commands_have_metadata(my_skill):
    for name, func in inspect.getmembers(my_skill, inspect.isfunction):
        if hasattr(func, "_is_skill_command"):
            assert hasattr(func, "_skill_config")
"""


# =============================================================================
# Tests for the skill management skill (using 'skill' fixture)
# =============================================================================


def test_skill_discover_exists(skill):
    """The discover command should exist in skill tools."""
    assert hasattr(skill, "discover")
    assert callable(skill.discover)


def test_skill_suggest_exists(skill):
    """The suggest command should exist."""
    assert hasattr(skill, "suggest")
    assert callable(skill.suggest)


def test_skill_jit_install_exists(skill):
    """The jit_install command should exist."""
    assert hasattr(skill, "jit_install")
    assert callable(skill.jit_install)


def test_skill_templates_exists(skill):
    """The templates command should exist."""
    assert hasattr(skill, "templates")
    assert callable(skill.templates)


def test_skill_list_index_exists(skill):
    """The list_index command should exist."""
    assert hasattr(skill, "list_index")
    assert callable(skill.list_index)


def test_skill_commands_have_metadata(skill):
    """All skill commands should have @skill_command metadata."""
    for name, func in inspect.getmembers(skill, inspect.isfunction):
        if hasattr(func, "_is_skill_command"):
            assert hasattr(func, "_skill_config")
            config = func._skill_config
            assert "name" in config
            assert "category" in config


def test_skill_tools_py_has_commands(skill):
    """skill/tools.py should have @skill_command decorated functions."""
    commands = [
        name
        for name, func in inspect.getmembers(skill, inspect.isfunction)
        if hasattr(func, "_is_skill_command")
    ]
    assert len(commands) > 0
    assert "templates" in commands
    assert "discover" in commands
    assert "suggest" in commands


def test_skill_templates_returns_string(skill):
    """templates command should return a string."""
    result = skill.templates(skill_name="git", action="list")

    # Handle CommandResult wrapper from @skill_command
    if hasattr(result, "data"):
        result = result.data if result.success else result.error

    assert isinstance(result, str)
    assert "git" in result.lower()
