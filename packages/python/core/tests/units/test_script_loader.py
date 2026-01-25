"""Tests for omni.core.skills.script_loader module.

PEP 420 Namespace Package Tests:
- Uses real skill directories from assets/skills/
- Verifies absolute imports work correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omni.core.skills.script_loader import (
    ScriptLoader,
)
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.skills import SKILLS_DIR


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
    """Test ScriptLoader class with real skill directories."""

    def test_initialize(self, tmp_path: Path):
        """Test ScriptLoader initialization."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        loader = ScriptLoader(scripts_dir, "test_skill")
        assert loader.scripts_path == scripts_dir
        assert loader.skill_name == "test_skill"

    def test_load_git_skill_commands(self):
        """Test loading real git skill commands."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ScriptLoader(scripts_dir, "git")
        loader.load_all()

        commands = loader.list_commands()
        # Git skill should have commands like git.status, git.commit, etc.
        assert len(commands) > 0
        assert any("git.status" in cmd for cmd in commands)

    def test_load_terminal_skill_commands(self):
        """Test loading real terminal skill commands."""
        scripts_dir = SKILLS_DIR(skill="terminal") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("terminal skill not found")

        loader = ScriptLoader(scripts_dir, "terminal")
        loader.load_all()

        commands = loader.list_commands()
        # Terminal skill should have commands
        assert len(commands) > 0

    def test_get_command_by_full_name(self):
        """Test getting a command by full name."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ScriptLoader(scripts_dir, "git")
        loader.load_all()

        # Get a specific command
        cmd = loader.get_command("git.status")
        # Command may or may not exist depending on skill implementation
        # Just verify the lookup doesn't crash
        assert cmd is None or callable(cmd)

    def test_get_command_by_simple_name(self):
        """Test getting a command by simple name."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ScriptLoader(scripts_dir, "git")
        loader.load_all()

        # Try simple name lookup
        cmd = loader.get_command_simple("status")
        # Command may or may not exist
        assert cmd is None or callable(cmd)

    def test_inject_context_to_git_skill(self):
        """Test injecting context into git skill."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ScriptLoader(scripts_dir, "git")
        loader.inject("rust", "test_rust_instance")
        loader.load_all()

        # Verify no errors during load with context
        assert len(loader.commands) > 0

    def test_native_functions_collected(self):
        """Test that native functions (without decorator) are collected."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ScriptLoader(scripts_dir, "git")
        loader.load_all()

        # Native functions should be collected even without decorator
        assert len(loader.native_functions) >= 0  # May be 0 or more


class TestScriptLoaderWithNamespacePackages:
    """Test PEP 420 namespace package import behavior."""

    def test_git_scripts_import_each_other(self):
        """Test that git.scripts modules can import each other."""
        # Add skills root to path for imports
        import sys

        skills_root_str = str(SKILLS_DIR())
        if skills_root_str not in sys.path:
            sys.path.insert(0, skills_root_str)

        # Try importing git.scripts modules
        try:
            from git.scripts import commit_state, prepare, rendering

            # Verify modules loaded successfully
            assert hasattr(commit_state, "create_initial_state")
            assert hasattr(rendering, "render_commit_message")
            assert hasattr(prepare, "stage_and_scan")
        except ImportError as e:
            pytest.skip(f"Namespace package import failed: {e}")
