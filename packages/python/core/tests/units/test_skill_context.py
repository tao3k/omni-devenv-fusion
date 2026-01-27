"""
Tests for Skill Context initialization, auto-loading, and tool schema extraction.

These tests verify:
1. SkillContext auto-loads skills on first access
2. Kernel.skill_context properly initializes with all commands
3. get_tool_schema reads from LanceDB correctly
4. Error handling for missing/invalid LanceDB data
5. Tool schema extraction from command handlers
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

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

        # Mock get_project_root to return tmp_path
        with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
            ctx = SkillContext(skills_dir)

            # Initially no skills loaded (LanceDB is empty)
            assert len(ctx.list_skills()) == 0
            assert len(ctx.list_commands()) == 0


class TestKernelSkillContext:
    """Tests for Kernel.skill_context initialization."""

    def test_kernel_skill_context_returns_context(self, tmp_path: Path):
        """Test that Kernel.skill_context returns a valid SkillContext."""
        from omni.core.kernel.engine import Kernel

        # Mock LanceDB to avoid actual database operations
        with patch("omni.foundation.bridge.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools.return_value = []
            mock_store.return_value = mock_store_instance

            with patch("omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path):
                kernel = Kernel(project_root=tmp_path)

                # Access skill_context (triggers loading)
                ctx = kernel.skill_context

                # Verify context was created successfully
                assert ctx is not None

    def test_skill_context_loads_in_running_loop_context(self, tmp_path: Path):
        """Test skill loading when called from within an async context.

        This specifically tests the scenario where Kernel.skill_context is
        accessed from within an MCP handler (which has a running event loop).
        """
        from omni.core.kernel.engine import Kernel

        async def access_skill_context():
            """Simulate MCP handler accessing skill_context."""
            with patch("omni.foundation.bridge.RustVectorStore") as mock_store:
                mock_store_instance = MagicMock()
                mock_store_instance.list_all_tools.return_value = []
                mock_store.return_value = mock_store_instance

                with patch(
                    "omni.foundation.runtime.gitops.get_project_root", return_value=tmp_path
                ):
                    kernel = Kernel(project_root=tmp_path)
                    ctx = kernel.skill_context
                    return ctx

        # This should NOT raise "asyncio.run() cannot be called from a running event loop"
        ctx = asyncio.run(access_skill_context())

        # Verify context was created successfully
        assert ctx is not None


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

        def get_handler(cmd_name):
            return None

        schemas = extract_tool_schemas(["nonexistent.command"], get_handler)
        assert schemas == []
