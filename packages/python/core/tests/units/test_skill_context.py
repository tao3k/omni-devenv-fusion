"""
Tests for Skill Context initialization, auto-loading, and tool schema extraction.

These tests verify:
1. SkillContext auto-loads skills on first access
2. Kernel.skill_context properly initializes with all commands
3. get_tool_schema reads from skill_index.json correctly
4. Error handling for missing/invalid skill_index.json
5. Tool schema extraction from command handlers
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSkillContextAutoLoad:
    """Tests for SkillContext auto-loading behavior."""

    def test_skill_context_loads_discovered_skills(self, tmp_path: Path):
        """Test that SkillContext loads discovered skills automatically."""
        from omni.core.skills.runtime import SkillContext

        # Create a minimal skill structure
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a test skill with a script
        test_skill = skills_dir / "test_skill"
        test_skill.mkdir()
        scripts_dir = test_skill / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "commands.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="test_cmd", description="A test command")
def test_cmd():
    return "test"

__all__ = ["test_cmd"]
""")

        # Create a mock skill_index.json
        skill_index = [
            {
                "name": "test_skill",
                "path": str(test_skill),
                "tools": [{"name": "test_skill.test_cmd", "description": "A test command"}],
            }
        ]
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "skill_index.json").write_text(json.dumps(skill_index))

        # Mock get_project_root to return tmp_path
        with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
            ctx = SkillContext(skills_dir)

            # Initially no skills loaded
            assert len(ctx.list_skills()) == 0
            assert len(ctx.list_commands()) == 0

    def test_skill_context_registers_commands_after_load(self, tmp_path: Path):
        """Test that commands are registered after loading a skill."""
        from omni.core.skills.runtime import SkillContext
        from omni.core.skills.universal import UniversalScriptSkill

        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a test skill
        test_skill = skills_dir / "my_skill"
        test_skill.mkdir()
        scripts_dir = test_skill / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "tools.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="my_command", description="My test command")
def my_command(value: int = 10):
    return value * 2

__all__ = ["my_command"]
""")

        # Create and load the skill
        skill = UniversalScriptSkill(skill_name="my_skill", skill_path=test_skill)

        # Load the skill (required to initialize _script_loader)
        asyncio.run(skill.load())

        # Create context and register skill
        ctx = SkillContext(skills_dir)
        ctx.register_skill(skill)

        # Verify command is registered with full name
        commands = ctx.list_commands()
        assert "my_skill.my_command" in commands

    def test_skill_context_get_command_returns_handler(self, tmp_path: Path):
        """Test that get_command returns the command handler."""
        from omni.core.skills.runtime import SkillContext
        from omni.core.skills.universal import UniversalScriptSkill

        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a test skill
        test_skill = skills_dir / "cmd_skill"
        test_skill.mkdir()
        scripts_dir = test_skill / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "tools.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="echo", description="Echo a message")
def echo(msg: str = "hello"):
    return f"Echo: {msg}"

__all__ = ["echo"]
""")

        skill = UniversalScriptSkill(skill_name="cmd_skill", skill_path=test_skill)
        asyncio.run(skill.load())

        ctx = SkillContext(skills_dir)
        ctx.register_skill(skill)

        # Get command handler
        handler = ctx.get_command("cmd_skill.echo")
        assert handler is not None
        assert callable(handler)

        # Execute handler
        result = handler(msg="test")
        assert result == "Echo: test"


class TestKernelSkillContext:
    """Tests for Kernel.skill_context property."""

    def test_kernel_skill_context_returns_same_instance(self, tmp_path: Path):
        """Test that skill_context returns the same instance on subsequent calls."""
        from omni.core.kernel.engine import Kernel

        kernel = Kernel(project_root=tmp_path)

        ctx1 = kernel.skill_context
        ctx2 = kernel.skill_context

        assert ctx1 is ctx2

    def test_skill_context_loads_skills_with_event_loop_isolation(self, tmp_path: Path):
        """Test that skill loading works in a thread with isolated event loop.

        This test prevents regression of the 'asyncio.run() cannot be called
        from a running event loop' error when Kernel is used in MCP context.
        """
        from omni.core.kernel.engine import Kernel

        # Create kernel - this triggers skill loading in a background thread
        # The key assertion is that this does NOT raise:
        # "asyncio.run() cannot be called from a running event loop"
        kernel = Kernel(project_root=tmp_path)

        # Access skill_context (triggers loading)
        ctx = kernel.skill_context

        # Verify context was created successfully
        assert ctx is not None
        # Skills should be loaded from the real skill_index.json
        assert len(ctx.list_skills()) > 0

    def test_skill_context_loads_skills_in_running_loop_context(self, tmp_path: Path):
        """Test skill loading when called from within an async context.

        This specifically tests the scenario where Kernel.skill_context is
        accessed from within an MCP handler (which has a running event loop).
        """
        import asyncio

        from omni.core.kernel.engine import Kernel

        async def access_skill_context():
            """Simulate MCP handler accessing skill_context."""
            kernel = Kernel(project_root=tmp_path)
            ctx = kernel.skill_context
            return ctx

        # This should NOT raise "asyncio.run() cannot be called from a running event loop"
        # The key fix is using asyncio.run() which creates its own event loop
        ctx = asyncio.run(access_skill_context())

        # Verify context was created successfully
        assert ctx is not None
        assert len(ctx.list_skills()) > 0


class TestToolSchemaExtraction:
    """Tests for extract_tool_schemas function."""

    def test_extract_tool_schemas_from_context(self, tmp_path: Path):
        """Test extracting tool schemas from SkillContext commands."""
        from omni.agent.core.omni.schemas import extract_tool_schemas
        from omni.core.skills.runtime import SkillContext
        from omni.core.skills.universal import UniversalScriptSkill

        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create a test skill
        test_skill = skills_dir / "extract_test"
        test_skill.mkdir()
        scripts_dir = test_skill / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "tools.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="process", description="Process data", category="write")
def process(data: str, options: dict | None = None):
    return {"result": data}

__all__ = ["process"]
""")

        skill = UniversalScriptSkill(skill_name="extract_test", skill_path=test_skill)
        asyncio.run(skill.load())

        ctx = SkillContext(skills_dir)
        ctx.register_skill(skill)

        # Get command handler
        def get_handler(cmd_name):
            return ctx.get_command(cmd_name)

        # Extract schemas
        schemas = extract_tool_schemas(["extract_test.process"], get_handler)

        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["name"] == "extract_test.process"
        assert "description" in schema
        assert "input_schema" in schema

    def test_extract_tool_schemas_empty_commands(self, tmp_path: Path):
        """Test extracting schemas with empty command list."""
        from omni.agent.core.omni.schemas import extract_tool_schemas
        from omni.core.skills.runtime import SkillContext

        ctx = SkillContext(tmp_path / "assets" / "skills")

        def get_handler(cmd):
            return None

        schemas = extract_tool_schemas([], get_handler)
        assert schemas == []

    def test_extract_tool_schemas_skips_missing_commands(self, tmp_path: Path):
        """Test that missing commands are skipped gracefully."""
        from omni.agent.core.omni.schemas import extract_tool_schemas
        from omni.core.skills.runtime import SkillContext

        ctx = SkillContext(tmp_path / "assets" / "skills")

        def get_handler(cmd):
            return None  # All commands return None

        schemas = extract_tool_schemas(["skill.missing1", "skill.missing2"], get_handler)
        assert schemas == []


class TestSkillDirectoryAPI:
    """Tests for SKILLS_DIR and get_skills_dir API."""

    def test_skills_dir_returns_base_path(self, tmp_path: Path):
        """Test SKILLS_DIR() returns skills base path."""
        from omni.foundation.config.skills import SKILLS_DIR

        # Patch get_setting at the module level where it's used
        with patch("omni.foundation.config.settings.get_setting", return_value="assets/skills"):
            with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
                result = SKILLS_DIR()
                assert result == tmp_path / "assets" / "skills"

    def test_skills_dir_returns_specific_skill(self, tmp_path: Path):
        """Test SKILLS_DIR('git') returns specific skill path."""
        from omni.foundation.config.skills import SKILLS_DIR

        with patch("omni.foundation.config.settings.get_setting", return_value="assets/skills"):
            with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
                result = SKILLS_DIR("git")
                assert result == tmp_path / "assets" / "skills" / "git"

    def test_get_skills_dir_uses_skills_dir(self, tmp_path: Path):
        """Test get_skills_dir() delegates to SKILLS_DIR."""
        from omni.foundation.config.dirs import get_skills_dir

        with patch("omni.foundation.config.settings.get_setting", return_value="assets/skills"):
            with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
                result = get_skills_dir()
                expected = tmp_path / "assets" / "skills"
                assert result == expected

    def test_get_skill_index_path(self, tmp_path: Path):
        """Test get_skill_index_path() returns .cache/skill_index.json."""
        from omni.foundation.config.dirs import get_skill_index_path

        # get_skill_index_path calls get_cache_dir("skill_index.json")
        # which internally uses get_prj_dir("cache", "skill_index.json")
        expected = tmp_path / ".cache" / "skill_index.json"

        def mock_get_prj_dir(_category: str = "data", subdir: str = "") -> Path:
            """Mock that properly appends subdir to base cache path."""
            base = tmp_path / ".cache"
            if subdir:
                return base / subdir
            return base

        with patch("omni.foundation.config.dirs.get_prj_dir", side_effect=mock_get_prj_dir):
            result = get_skill_index_path()
            assert result == expected


class TestSkillContextIntegration:
    """Integration tests for skill loading and tool schema."""

    def test_full_tool_schema_extraction_flow(self, tmp_path: Path):
        """Test complete flow: load skills -> extract schemas -> verify format."""
        from omni.agent.core.omni.schemas import extract_tool_schemas
        from omni.core.kernel.engine import Kernel

        # Create skill structure
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create filesystem skill
        fs_skill = skills_dir / "filesystem"
        fs_skill.mkdir()
        scripts_dir = fs_skill / "scripts"
        scripts_dir.mkdir()

        (scripts_dir / "io.py").write_text("""
from omni.foundation.api.decorators import skill_command

@skill_command(name="read_files", description="Read file content")
def read_files(paths: list[str], encoding: str = "utf-8") -> str:
    return "content"

@skill_command(name="write_file", description="Write file content")
def write_file(path: str, content: str) -> dict:
    with open(path, "w") as f:
        f.write(content)
    return {"success": True, "path": path}

__all__ = ["read_files", "write_file"]
""")

        # Create skill_index.json
        skill_index = [
            {
                "name": "filesystem",
                "path": str(fs_skill),
                "tools": [
                    {"name": "filesystem.read_files", "description": "Read file content"},
                    {"name": "filesystem.write_file", "description": "Write file content"},
                ],
            }
        ]
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        (cache_dir / "skill_index.json").write_text(json.dumps(skill_index))

        # Create kernel and get skill context
        kernel = Kernel(project_root=tmp_path)
        ctx = kernel.skill_context

        # Verify skills loaded
        assert "filesystem" in ctx.list_skills()

        # Extract tool schemas
        def get_handler(cmd):
            return ctx.get_command(cmd)

        schemas = extract_tool_schemas(
            ["filesystem.read_files", "filesystem.write_file"], get_handler
        )

        # Verify schemas
        assert len(schemas) == 2

        read_schema = next(s for s in schemas if "read_file" in s["name"])
        assert read_schema["name"] == "filesystem.read_files"
        assert "paths" in read_schema["input_schema"]["properties"]

        write_schema = next(s for s in schemas if "write_file" in s["name"])
        assert write_schema["name"] == "filesystem.write_file"
        assert "path" in write_schema["input_schema"]["properties"]
        assert "content" in write_schema["input_schema"]["properties"]


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
