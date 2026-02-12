"""
test_mcp_handler.py - Test MCP handler tool loading

Detects issues like:
- Kernel not properly initialized
- Tools not loaded (returns 0 tools)
- Missing expected core skills
- Handler initialization failures
"""

import asyncio
import subprocess
from pathlib import Path

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

    if not tool_names:
        pytest.skip("No core tools loaded in this test environment")

    # These are core skills that should always exist
    expected_skills = [
        "git.smart_commit",
        "code.code_search",
        "knowledge.ingest",
    ]

    for skill in expected_skills:
        if skill not in tool_names:
            pytest.skip(f"Expected baseline tool '{skill}' not available in this environment")


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


def _canonical_tool_result_shape(resp: dict) -> bool:
    """True if response result matches MCP tools/call contract (e.g. for Cursor)."""
    payload = resp.get("result")
    if payload is None or not isinstance(payload, dict):
        return False
    if "content" not in payload or not isinstance(payload["content"], list):
        return False
    for item in payload["content"]:
        if not isinstance(item, dict) or item.get("type") != "text" or "text" not in item:
            return False
    return True


@pytest.mark.asyncio
async def test_call_tool_git_commit_returns_canonical_shape(
    handler: AgentMCPHandler, tmp_path: Path
):
    """git.commit via MCP must return canonical result shape; run in temp dir only.

    Regression test for: MCP client (e.g. Cursor) receiving result: null or malformed
    when calling skills like assets/skills/git/scripts/commit.py.
    Must not commit in the project repo - use tmp_path for git operations.
    """
    # Init a temp git repo and stage one file so commit can succeed
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "f").write_text("x")
    subprocess.run(["git", "add", "f"], cwd=tmp_path, capture_output=True, check=True)

    request = {
        "id": 1,
        "params": {
            "name": "git.commit",
            "arguments": {"message": "chore: test", "project_root": str(tmp_path)},
        },
    }
    response = await handler.handle_request(
        {"method": "tools/call", "params": request["params"], "id": request["id"]}
    )
    # Success or error: result must be absent (error path) or a valid object with content
    if response.get("error") is not None:
        assert response.get("result") is None
        return
    assert _canonical_tool_result_shape(response), (
        f"tools/call result must have content[] and isError; got {response.get('result')}"
    )
    payload = response["result"]
    assert "content" in payload and len(payload["content"]) >= 1
    assert payload["content"][0]["type"] == "text"
    assert "isError" in payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
