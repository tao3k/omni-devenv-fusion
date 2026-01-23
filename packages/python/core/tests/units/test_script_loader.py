"""Tests for omni.core.skills.script_loader module.

Uses Foundation V2 @skill_command decorator from omni.foundation.api.decorators.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from omni.foundation.api.decorators import skill_command
from omni.core.skills.script_loader import (
    ScriptLoader,
    _skill_command_registry,
)


class TestSkillCommand:
    """Test skill_command decorator (V2 from foundation)."""

    def test_basic_decorator(self):
        """Test basic decorator usage."""

        @skill_command(name="test_cmd", description="A test command")
        def test_function():
            return "test"

        # The decorator sets _is_skill_command and _skill_config
        assert hasattr(test_function, "_is_skill_command")
        assert test_function._is_skill_command is True
        assert hasattr(test_function, "_skill_config")
        assert test_function._skill_config["name"] == "test_cmd"
        assert test_function._skill_config["description"] == "A test command"

    def test_decorator_with_args(self):
        """Test decorator with parameters."""

        @skill_command(
            name="args_cmd",
            category="test",
            description="Command with args",
        )
        def cmd_with_args(value: int, name: str = "default"):
            return f"{name}: {value}"

        result = cmd_with_args(42, name="test")
        assert result == "test: 42"


class TestScriptLoader:
    """Test ScriptLoader class."""

    def test_initialize(self, tmp_path: Path):
        """Test ScriptLoader initialization."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        loader = ScriptLoader(scripts_dir, "test_skill")
        assert loader.scripts_path == scripts_dir
        assert loader.skill_name == "test_skill"

    def test_load_single_script(self, tmp_path: Path):
        """Test loading a single script file."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Create a test script with @skill_command decorator (V2)
        (scripts_dir / "example.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="hello", description="Say hello")
def hello():
    return "Hello from example!"

__all__ = ["hello"]
""")

        loader = ScriptLoader(scripts_dir, "test")
        loader.load_all()

        assert "test.hello" in loader.list_commands()

    def test_inject_context(self, tmp_path: Path):
        """Test context injection."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "context_test.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="get_rust", description="Get rust context")
def get_rust():
    return rust

__all__ = ["get_rust"]
""")

        loader = ScriptLoader(scripts_dir, "test")
        loader.inject("rust", "rust_accelerator_instance")
        loader.load_all()

        assert loader.get_command("test.get_rust") is not None

    def test_get_command(self, tmp_path: Path):
        """Test getting a command."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "my_script.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="my_command", description="Multiply value")
def my_command(value: int = 10):
    return value * 2

__all__ = ["my_command"]
""")

        loader = ScriptLoader(scripts_dir, "test")
        loader.load_all()

        cmd = loader.get_command("test.my_command")
        assert cmd is not None
        assert cmd() == 20
        assert cmd(value=5) == 10

    def test_list_commands(self, tmp_path: Path):
        """Test listing commands."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "cmd1.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd1", description="Command 1")
def cmd1():
    return "cmd1"
__all__ = ["cmd1"]
""")
        (scripts_dir / "cmd2.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd2", description="Command 2")
def cmd2():
    return "cmd2"
__all__ = ["cmd2"]
""")

        loader = ScriptLoader(scripts_dir, "test")
        loader.load_all()

        commands = loader.list_commands()
        assert len(commands) == 2
        assert "test.cmd1" in commands
        assert "test.cmd2" in commands
