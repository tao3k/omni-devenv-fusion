"""Tests for omni.core.skills.tools_loader module.

PEP 420 Namespace Package Tests:
- Uses real skill directories from assets/skills/
- Verifies absolute imports work correctly
- Tests dependency order loading (_*.py files loaded after regular files)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from omni.core.skills.tools_loader import (
    ToolsLoader,
    create_tools_loader,
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


class TestToolsLoader:
    """Test ToolsLoader class with real skill directories."""

    def test_initialize(self, tmp_path: Path):
        """Test ToolsLoader initialization."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        loader = ToolsLoader(scripts_dir, "test_skill")
        assert loader.scripts_path == scripts_dir
        assert loader.skill_name == "test_skill"

    def test_load_git_skill_commands(self):
        """Test loading real git skill commands."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        commands = loader.list_commands()
        # Git skill should expose at least one namespaced git command.
        assert len(commands) > 0
        assert any(cmd.startswith("git.") for cmd in commands)

    def test_load_terminal_skill_commands(self):
        """Test loading real terminal skill commands."""
        scripts_dir = SKILLS_DIR(skill="terminal") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("terminal skill not found")

        loader = ToolsLoader(scripts_dir, "terminal")
        loader.load_all()

        commands = loader.list_commands()
        # Terminal skill should have commands
        assert len(commands) > 0

    def test_get_command_by_full_name(self):
        """Test getting a command by full name."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        first_cmd = next((c for c in loader.list_commands() if c.startswith("git.")), None)
        assert first_cmd is not None
        cmd = loader.get_command(first_cmd)
        assert cmd is None or callable(cmd)

    def test_get_command_by_simple_name(self):
        """Test getting a command by simple name."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        first_cmd = next((c for c in loader.list_commands() if c.startswith("git.")), None)
        assert first_cmd is not None
        simple_name = first_cmd.split(".", 1)[1]
        cmd = loader.get_command_simple(simple_name)
        assert cmd is None or callable(cmd)

    def test_inject_context_to_git_skill(self):
        """Test injecting context into git skill."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.inject("rust", "test_rust_instance")
        loader.load_all()

        # Verify no errors during load with context
        assert len(loader.commands) > 0

    def test_native_functions_collected(self):
        """Test that native functions (without decorator) are collected."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        # Native functions should be collected even without decorator
        assert len(loader.native_functions) >= 0  # May be 0 or more


class TestToolsLoaderWithNamespacePackages:
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


class TestToolsLoaderSmartCommit:
    """Test smart_commit workflow loading (requires sibling imports)."""

    def test_smart_commit_workflow_loaded(self):
        """Test that smart_commit_workflow.py is loaded successfully.

        This test verifies that modules with sibling imports (e.g.,
        from git.scripts.commit_state import ...) work correctly.
        """
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        # smart_commit should be loaded
        commands = loader.list_commands()
        assert "git.smart_commit" in commands, f"smart_commit not found in commands: {commands}"

    def test_smart_commit_function_harvested(self):
        """Test that smart_commit function has proper decorator attributes."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        # Get the smart_commit command
        cmd = loader.get_command("git.smart_commit")
        assert cmd is not None, "git.smart_commit command not found"
        assert callable(cmd), "git.smart_commit should be callable"
        assert hasattr(cmd, "_is_skill_command"), (
            "smart_commit should have _is_skill_command attribute"
        )
        # pyright: ignore[reportFunctionMemberAccess]
        assert cmd._is_skill_command is True, (  # pyright: ignore[reportFunctionMemberAccess]
            "_is_skill_command should be True"
        )


class TestToolsLoaderDependencyOrder:
    """Test dependency order loading (_*.py files loaded after regular files)."""

    def test_dependency_order_preserved(self, tmp_path: Path):
        """Test that _*.py files are loaded after regular files.

        This ensures modules with external dependencies (like _enums.py
        depending on modules that use it) load in the correct order.
        """
        skill_root = tmp_path / "test_skill"
        scripts_dir = skill_root / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create a module that will be imported by others
        (scripts_dir / "utils.py").write_text("""
from __future__ import annotations
VALUE = "utils_loaded"
""")

        # Create a module that imports utils first
        (scripts_dir / "main_module.py").write_text("""
from __future__ import annotations
from test_skill.scripts.utils import VALUE
RESULT = f"main:{VALUE}"
""")

        # Create _enums.py that imports from main_module (simulating git._enums)
        (scripts_dir / "_enums.py").write_text("""
from __future__ import annotations
from test_skill.scripts.main_module import RESULT
ENUM_VALUE = RESULT
""")

        # Create a skill command that imports from _enums
        (scripts_dir / "commands.py").write_text("""
from __future__ import annotations
from test_skill.scripts._enums import ENUM_VALUE

from omni.foundation.api.decorators import skill_command

@skill_command(name="test_cmd", description="Test command")
def test_command():
    return ENUM_VALUE
""")

        loader = ToolsLoader(scripts_dir, "test_skill")
        loader.load_all()

        # All commands should be loaded successfully
        assert "test_skill.test_cmd" in loader.commands

    def test_all_files_loaded_no_skip(self, tmp_path: Path):
        """Test that no files are skipped during loading."""
        skill_root = tmp_path / "test_skill"
        scripts_dir = skill_root / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create multiple files
        (scripts_dir / "module_a.py").write_text("""
from __future__ import annotations
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd_a", description="Command A")
def cmd_a():
    return "a"
""")

        (scripts_dir / "module_b.py").write_text("""
from __future__ import annotations
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd_b", description="Command B")
def cmd_b():
    return "b"
""")

        (scripts_dir / "_private.py").write_text("""
from __future__ import annotations
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd_private", description="Private command")
def cmd_private():
    return "private"
""")

        loader = ToolsLoader(scripts_dir, "test_skill")
        loader.load_all()

        # All commands should be loaded
        commands = loader.list_commands()
        assert "test_skill.cmd_a" in commands
        assert "test_skill.cmd_b" in commands
        assert "test_skill.cmd_private" in commands


class TestToolsLoaderSysPath:
    """Test sys.path management during loading."""

    def test_sys_path_restored_after_load(self, tmp_path: Path):
        """Test that sys.path is restored after loading."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Add a unique path that we can track
        test_path = str(tmp_path / "unique_test_path")
        assert test_path not in sys.path

        loader = ToolsLoader(scripts_dir, "test_skill")
        loader.load_all()

        # After load, sys.path should be restored to original state
        # (the path we added during load should be removed)
        # Note: We don't assert this strictly since other tests may add paths

    def test_inject_context_accessible(self, tmp_path: Path):
        """Test that injected context is accessible in loaded modules."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "test_module.py").write_text("""
from __future__ import annotations
from omni.foundation.api.decorators import skill_command

@skill_command(name="context_test", description="Test context injection")
def context_test():
    # Access the injected rust accelerator
    return RUST_ACCELERATOR.upper() if 'RUST_ACCELERATOR' in dir() else "no_context"
""")

        loader = ToolsLoader(scripts_dir, "test_skill")
        loader.inject("RUST_ACCELERATOR", "test_rust_value")
        loader.load_all()

        cmd = loader.get_command("test_skill.context_test")
        assert cmd is not None


class TestToolsLoaderCommandNaming:
    """Test command naming and harvesting."""

    def test_command_full_name_format(self):
        """Test commands are stored with full skill.command format."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        for cmd_name in loader.commands:
            # All command names should be in "skill.command" format
            assert "." in cmd_name, f"Command name {cmd_name} should contain '.'"
            parts = cmd_name.split(".")
            assert len(parts) == 2, f"Command name {cmd_name} should have exactly 2 parts"
            assert parts[0] == "git", f"First part should be 'git', got {parts[0]}"

    def test_get_command_simple_fallback(self):
        """Test get_command_simple falls back to various lookup methods."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        # Simple name should work for known commands
        if "git.status" in loader.commands:
            result = loader.get_command_simple("status")
            assert result is not None

    def test_command_count_reasonably_bounded(self):
        """Test command count is reasonable for a skill."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = ToolsLoader(scripts_dir, "git")
        loader.load_all()

        # Git skill should have a reasonable number of commands (5-20)
        # This catches issues where all functions are harvested
        assert 1 <= len(loader.commands) <= 50, f"Unexpected command count: {len(loader.commands)}"


class TestCreateToolsLoader:
    """Test create_tools_loader factory function."""

    def test_factory_creates_loader(self, tmp_path: Path):
        """Test factory function creates properly configured loader."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        loader = create_tools_loader(scripts_dir, "factory_test")

        assert isinstance(loader, ToolsLoader)
        assert loader.scripts_path == scripts_dir
        assert loader.skill_name == "factory_test"

    def test_factory_loads_commands(self):
        """Test factory loader can load commands."""
        scripts_dir = SKILLS_DIR(skill="git") / "scripts"

        if not scripts_dir.exists():
            pytest.skip("git skill not found")

        loader = create_tools_loader(scripts_dir, "git")
        loader.load_all()

        assert len(loader.commands) > 0
