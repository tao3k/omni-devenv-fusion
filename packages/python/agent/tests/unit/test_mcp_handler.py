"""
test_mcp_handler.py - Test MCP handler tool loading

Detects issues like:
- Kernel not properly initialized
- Tools not loaded (returns 0 tools)
- Missing expected core skills
- Handler initialization failures
"""

import asyncio
import pytest

from omni.agent.server import AgentMCPHandler


@pytest.fixture
async def handler():
    """Create and initialize MCP handler."""
    handler = AgentMCPHandler()
    await handler.initialize()
    yield handler
    # Cleanup if needed


@pytest.mark.asyncio
async def test_kernel_is_ready(handler: AgentMCPHandler):
    """Ensure kernel is ready after initialization."""
    assert handler._kernel.is_ready, "Kernel should be ready after initialize()"


@pytest.mark.asyncio
async def test_tools_not_empty(handler: AgentMCPHandler):
    """Ensure at least some tools are loaded."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])

    assert len(tools) > 0, f"Expected tools, got {len(tools)}"
    # Sanity check: should have at least 10 tools
    assert len(tools) >= 10, f"Expected >= 10 tools, got {len(tools)}"


@pytest.mark.asyncio
async def test_expected_skills_exist(handler: AgentMCPHandler):
    """Ensure core skills are loaded."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}

    # These are core skills that should always exist
    expected_skills = [
        "git.smart_commit",
        "code_tools.smart_ast_search",
        "knowledge.ingest",
    ]

    for skill in expected_skills:
        assert skill in tool_names, f"Expected skill '{skill}' not found in tools"


@pytest.mark.asyncio
async def test_tools_have_required_fields(handler: AgentMCPHandler):
    """Ensure all tools have required MCP fields."""
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])

    for tool in tools:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool '{tool['name']}' missing 'description'"
        assert "inputSchema" in tool, f"Tool '{tool['name']}' missing 'inputSchema'"


@pytest.mark.asyncio
async def test_tools_list_format(handler: AgentMCPHandler):
    """Ensure tools/list response is correctly formatted."""
    result = await handler._handle_list_tools({"id": 42})

    # Check response structure
    assert "result" in result, "Response missing 'result'"
    assert "tools" in result["result"], "Response missing 'result.tools'"
    assert isinstance(result["result"]["tools"], list), "result.tools should be a list"


@pytest.mark.asyncio
async def test_double_init_no_error(handler: AgentMCPHandler):
    """Ensure calling initialize() twice doesn't cause errors."""
    # First init already done by fixture
    await handler.initialize()  # Second init should be no-op
    await handler.initialize()  # Third init

    # Should still work
    result = await handler._handle_list_tools({"id": 1})
    tools = result.get("result", {}).get("tools", [])
    assert len(tools) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
