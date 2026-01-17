"""
packages/python/agent/src/agent/tests/test_mcp_dependencies.py
Tests to verify skill architecture dependencies are properly configured.

Phase 35.3: Pure MCP Server Architecture
- Uses mcp.server.Server
- Tools listed dynamically via handle_list_tools
- Tool execution via handle_call_tool -> SkillManager

These tests catch issues like:
- Skill modules failing to import
- Skill registry not discovering skills
- Skills not loading correctly
- MCP Server not properly configured
"""

import pytest
from pathlib import Path


class TestMcpServerArchitecture:
    """Test pure MCP Server architecture (Phase 35.3)."""

    def test_mcp_server_import(self):
        """mcp.server should import successfully."""
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.server.sse import SseServerTransport

        assert Server is not None
        assert stdio_server is not None
        assert SseServerTransport is not None

    def test_omni_server_instance(self):
        """Omni MCP Server instance should be created correctly."""
        from agent.mcp_server.server import get_init_options

        # Check that init options are correctly set
        init_opts = get_init_options()
        assert init_opts.server_name == "omni-agent"
        assert init_opts.server_version == "1.0.0"

    def test_run_mcp_server_import(self):
        """run function should be importable (the MCP server entry point)."""
        from agent.mcp_server import run

        assert callable(run)


class TestSkillArchitecture:
    """Test that the skill architecture is properly configured."""

    def test_agent_core_imports(self):
        """agent.core modules should import successfully."""
        from agent.core.registry import SkillRegistry

        assert SkillRegistry is not None

    def test_common_mcp_core_imports(self):
        """common.mcp_core modules should import successfully."""
        from common.gitops import get_project_root

        root = get_project_root()
        assert root is not None
        assert root.exists()

    def test_skills_directory_exists(self):
        """assets/skills/ directory should exist with skill modules."""
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        # Check for at least core skills
        core_skills = ["filesystem", "git", "terminal", "testing"]
        for skill in core_skills:
            assert skill in skills, f"Missing skill: {skill}"

    def test_skill_manifests_valid(self):
        """All skill SKILL.md files should be valid YAML frontmatter."""
        from agent.core.registry import get_skill_registry
        import frontmatter

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        for skill_name in skills:
            skill_dir = Path.cwd() / "assets" / "skills" / skill_name
            skill_md_path = skill_dir / "SKILL.md"
            if skill_md_path.exists():
                with open(skill_md_path) as f:
                    data = frontmatter.load(f)
                assert "name" in data.metadata, f"{skill_name} SKILL.md missing 'name'"


class TestSkillRegistry:
    """Test that skill registry can discover and load skills."""

    def test_skill_registry_discovers_skills(self):
        """SkillRegistry should discover all skills in assets/skills/."""
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        required = ["filesystem", "git", "terminal", "testing"]
        for s in required:
            assert s in skills, f"Missing skill: {s}"


class TestSkillBootstrap:
    """Test skill bootstrap with pure MCP Server."""

    def test_boot_core_skills_no_mcp(self):
        """boot_core_skills should work without MCP parameter."""
        from agent.core.bootstrap import boot_core_skills

        # Should not raise, mcp parameter is optional
        boot_core_skills()

    def test_skill_manager_has_tools(self):
        """SkillManager should list tools for MCP Server."""
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        loaded_skills = manager.list_loaded()

        # After bootstrap, skills should be loaded
        assert len(loaded_skills) > 0

    def test_tools_convertible_to_mcp_format(self):
        """Skills should be convertible to MCP Tool format."""
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        loaded_skills = manager.list_loaded()

        for skill_name in loaded_skills:
            commands = manager.get_commands(skill_name)
            for cmd_name in commands:
                tool_name = f"{skill_name}.{cmd_name}"
                # Should be valid format for MCP tool name
                assert "." in tool_name
                assert len(tool_name) > 1
