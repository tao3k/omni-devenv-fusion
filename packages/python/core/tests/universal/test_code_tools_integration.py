import pytest
import asyncio
from pathlib import Path
from omni.core.kernel.engine import get_kernel


@pytest.fixture
async def kernel():
    """Fixture to provide an initialized kernel and ensure it's shut down."""
    k = get_kernel()
    await k.initialize()
    yield k
    await k.shutdown()


@pytest.mark.asyncio
async def test_code_search_integration(kernel):
    """Integration test: Verify code.code_search discovery and execution."""

    # 1. Verify Discovery
    skill = kernel.skill_context.get_skill("code")
    assert skill is not None

    commands = skill.list_commands()
    assert "code.code_search" in commands

    # 2. Verify Execution returns structured response (even if no results)
    result = await kernel.execute_tool(
        "code.code_search",
        {"query": "class NonExistentClassXYZ123"},
    )

    # Should return XML-formatted response
    assert "<search_interaction" in result or "SEARCH:" in result

    # 3. Verify Session ID parameter works
    result_with_session = await kernel.execute_tool(
        "code.code_search",
        {"query": "how does code search work", "session_id": "test_session"},
    )
    assert result_with_session  # Should return some response


@pytest.mark.asyncio
async def test_modular_relative_imports_integration(kernel):
    """Verify that relative imports work correctly in the actual skill directory."""

    # Execute the search tool which relies on 'from .graph import execute_search'
    # If the relative import failed, this tool call would raise an exception
    try:
        result = await kernel.execute_tool(
            "code.code_search",
            {"query": "code search function"},
        )
        # Verify we got a response (no import error)
        assert result is not None
        assert "<search_interaction" in result or "SEARCH:" in result
    except Exception as e:
        pytest.fail(f"Tool execution failed due to modular import error: {e}")
