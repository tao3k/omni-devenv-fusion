"""
Template Skill Tests - Phase 35.1

Usage:
    uv run pytest assets/skills/_template/tests/ -v
    omni skill test _template

Tests cover:
- example: Example command with parameter
- example_with_options: Example with optional parameters
- process_data: Process a list of data strings
"""

import pytest
import inspect
import sys
import types
import importlib.util
from pathlib import Path


def _setup_template_package_context():
    """Set up the package hierarchy in sys.modules for template skill."""
    tests_dir = Path(__file__).parent  # assets/skills/_template/tests
    template_dir = tests_dir.parent  # assets/skills/_template
    skills_root = template_dir.parent  # assets/skills
    project_root = skills_root.parent.parent  # project root

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

    # Ensure 'agent.skills._template' package exists
    template_pkg_name = "agent.skills._template"
    if template_pkg_name not in sys.modules:
        template_pkg = types.ModuleType(template_pkg_name)
        template_pkg.__path__ = [str(template_dir)]
        template_pkg.__file__ = str(template_dir / "__init__.py")
        sys.modules[template_pkg_name] = template_pkg

    # Ensure 'agent.skills._template.scripts' package exists
    scripts_pkg_name = "agent.skills._template.scripts"
    if scripts_pkg_name not in sys.modules:
        scripts_dir = template_dir / "scripts"
        scripts_pkg = types.ModuleType(scripts_pkg_name)
        scripts_pkg.__path__ = [str(scripts_dir)]
        scripts_pkg.__file__ = str(scripts_dir / "__init__.py")
        sys.modules[scripts_pkg_name] = scripts_pkg

    # Pre-load decorators module for @skill_script support
    decorators_name = "agent.skills.decorators"
    if decorators_name not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = importlib.util.spec_from_file_location(decorators_name, str(decorators_path))
            if spec and spec.loader:
                decorators_mod = importlib.util.module_from_spec(spec)
                sys.modules[decorators_name] = decorators_mod
                spec.loader.exec_module(decorators_mod)


# Setup package context before importing
_setup_template_package_context()


# =============================================================================
# Command Existence Tests
# =============================================================================


def test_example_exists():
    """Verify example command exists and is callable."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "example")
    assert callable(commands.example)


def test_example_with_options_exists():
    """Verify example_with_options command exists."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "example_with_options")
    assert callable(commands.example_with_options)


def test_process_data_exists():
    """Verify process_data command exists."""
    from agent.skills._template.scripts import commands

    assert hasattr(commands, "process_data")
    assert callable(commands.process_data)


# =============================================================================
# Command Execution Tests
# =============================================================================


def test_example_default_param():
    """Test example command with default parameter."""
    from agent.skills._template.scripts import commands

    result = commands.example()
    assert isinstance(result, str)
    assert "Example" in result


def test_example_custom_param():
    """Test example command with custom parameter."""
    from agent.skills._template.scripts import commands

    result = commands.example(param="test_value")
    assert isinstance(result, str)
    assert "test_value" in result


def test_example_with_options_defaults():
    """Test example_with_options with default values."""
    from agent.skills._template.scripts import commands

    result = commands.example_with_options()
    assert isinstance(result, dict)
    assert result["enabled"] is True
    assert result["value"] == 42


def test_example_with_options_custom():
    """Test example_with_options with custom values."""
    from agent.skills._template.scripts import commands

    result = commands.example_with_options(enabled=False, value=100)
    assert isinstance(result, dict)
    assert result["enabled"] is False
    assert result["value"] == 100


def test_process_data_no_filter():
    """Test process_data without filtering empty strings."""
    from agent.skills._template.scripts import commands

    data = ["a", "", "b", "", "c"]
    result = commands.process_data(data, filter_empty=False)
    assert result == ["a", "", "b", "", "c"]


def test_process_data_with_filter():
    """Test process_data with empty string filtering."""
    from agent.skills._template.scripts import commands

    data = ["a", "", "b", "", "c"]
    result = commands.process_data(data, filter_empty=True)
    assert result == ["a", "b", "c"]


def test_process_data_empty_list():
    """Test process_data with empty input list."""
    from agent.skills._template.scripts import commands

    result = commands.process_data([])
    assert result == []
