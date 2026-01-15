"""
packages/python/agent/src/agent/tests/unit/test_list_tools.py
Regression test for Phase 73: list_tools must return all skill commands.

Issue: handle_list_tools() was using adaptive_loader.get_context_tools() with empty
query, which only returned Core Tools (from settings.yaml) and skipped all other
skill commands. This caused git.* commands to not appear in tool list.

Test guarantees:
- handle_list_tools() returns ALL commands from ALL loaded skills
- handle_list_tools() includes the omni meta-tool
- No skill commands are silently dropped
"""

import pytest
import pytest_asyncio


class TestListToolsRegression:
    """Regression tests for list_tools functionality (Phase 73)."""

    @pytest_asyncio.fixture
    async def loaded_manager(self):
        """Get a skill manager with skills loaded."""
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        if not manager._loaded:
            await manager.load_all()
        yield manager
        # Cleanup: reset loaded state for other tests
        manager._loaded = False

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_skill_commands(self, loaded_manager):
        """
        CRITICAL: list_tools must return ALL skill commands, not just Core Tools.

        This was the Phase 73 bug: get_context_tools(user_query="") only returned
        Core Tools from settings.yaml, silently dropping all other skill commands.
        """
        from agent.mcp_server import handle_list_tools

        tools = await handle_list_tools()
        tool_names = {t.name for t in tools}

        # All loaded skill commands must be in the list
        for skill_name, skill in loaded_manager.skills.items():
            for cmd_name in skill.commands.keys():
                expected_tool = f"{skill_name}.{cmd_name}"
                assert expected_tool in tool_names, (
                    f"Skill command missing from list_tools: {expected_tool}. "
                    "This indicates a regression where only Core Tools are returned."
                )

    @pytest.mark.asyncio
    async def test_list_tools_includes_omni_meta_tool(self, loaded_manager):
        """list_tools must always include the omni meta-tool."""
        from agent.mcp_server import handle_list_tools

        tools = await handle_list_tools()
        tool_names = {t.name for t in tools}

        assert "omni" in tool_names, (
            "omni meta-tool must be in list_tools output. "
            "This tool is required for skill.command execution."
        )

    @pytest.mark.asyncio
    async def test_list_tools_no_missing_commands(self, loaded_manager):
        """
        Verify count matches: all skill commands + omni should equal tool count.

        This catches cases where some commands are silently dropped.
        """
        from agent.mcp_server import handle_list_tools

        tools = await handle_list_tools()

        # Count expected commands from all loaded skills
        expected_skill_commands = sum(
            len(skill.commands) for skill in loaded_manager.skills.values()
        )
        expected_total = expected_skill_commands + 1  # +1 for omni

        actual_count = len(tools)

        assert actual_count == expected_total, (
            f"Tool count mismatch: expected {expected_total} "
            f"(={expected_skill_commands} skill commands + omni), "
            f"got {actual_count}. Some commands may have been dropped."
        )

    @pytest.mark.asyncio
    async def test_list_tools_with_empty_query_returns_all(self):
        """
        Even with user_query="", list_tools must return ALL commands.

        The old implementation used get_context_tools(user_query="") which
        returned nothing for dynamic tools. This test ensures the fix works.

        Note: The actual count depends on how many skills are loaded.
        At minimum, we should have all commands from loaded skills + omni.
        """
        from agent.mcp_server import handle_list_tools
        from agent.core.skill_manager import get_skill_manager

        tools = await handle_list_tools()
        manager = get_skill_manager()

        # Calculate expected count from loaded skills
        expected_skill_commands = sum(len(skill.commands) for skill in manager.skills.values())
        expected_total = expected_skill_commands + 1  # +1 for omni

        # Verify all commands are returned
        assert len(tools) == expected_total, (
            f"list_tools returned {len(tools)} tools, expected {expected_total}. "
            "This suggests a regression to adaptive_loader behavior."
        )

    @pytest.mark.asyncio
    async def test_list_tools_tool_schemas_valid(self, loaded_manager):
        """Each tool from list_tools should have valid MCP schema."""
        from agent.mcp_server import handle_list_tools

        tools = await handle_list_tools()

        for tool in tools:
            # Name must be non-empty
            assert tool.name, f"Tool with empty name found"
            assert isinstance(tool.name, str), f"Tool name must be string, got {type(tool.name)}"

            # Description should exist
            assert tool.description, f"Tool {tool.name} missing description"

            # inputSchema must be dict
            assert isinstance(tool.inputSchema, dict), (
                f"Tool {tool.name} inputSchema must be dict, got {type(tool.inputSchema)}"
            )


class TestListToolsDoesNotUseAdaptiveLoader:
    """
    Verify list_tools bypasses adaptive_loader for full listing.

    The bug was that handle_list_tools() delegated to get_context_tools()
    which only returns Core Tools + dynamic matches. For full listing,
    we must iterate over manager.skills directly.
    """

    @pytest.mark.asyncio
    async def test_handle_list_tools_skips_adaptive_loader(self):
        """
        handle_list_tools should NOT use get_context_tools for full listing.

        This is a structural test to prevent future regressions.
        """
        from agent.mcp_server import handle_list_tools
        import inspect

        # Get the source code of handle_list_tools
        source = inspect.getsource(handle_list_tools)

        # Should NOT call get_context_tools (the problematic function)
        # This prevents someone from "fixing" it by switching back to adaptive_loader
        assert "get_context_tools" not in source, (
            "handle_list_tools should NOT use get_context_tools. "
            "That function only returns Core Tools + dynamic matches. "
            "Use manager.skills directly for full listing."
        )

    @pytest.mark.asyncio
    async def test_handle_list_tools_iterates_skills_directly(self):
        """
        handle_list_tools must iterate over manager.skills directly.

        This ensures all loaded skills are listed, not filtered by any criteria.
        """
        from agent.mcp_server import handle_list_tools
        import inspect

        source = inspect.getsource(handle_list_tools)

        # Should access skills from manager
        assert "manager.skills" in source or "manager._skills" in source, (
            "handle_list_tools must iterate over manager.skills directly "
            "to get all commands from all loaded skills."
        )
