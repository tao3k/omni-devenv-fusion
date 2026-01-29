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
async def test_smart_ast_search_integration(kernel):
    """Integration test: Verify code_tools.smart_ast_search discovery and execution."""

    # 1. Verify Discovery
    skill = kernel.skill_context.get_skill("code_tools")
    assert skill is not None

    commands = skill.list_commands()
    assert "code_tools.smart_ast_search" in commands

    # 2. Verify Execution (Real AST Search)
    # We search for the SmartSearchEngine class definition within the project
    result = await kernel.execute_tool(
        "code_tools.smart_ast_search",
        {
            "query": "class SmartSearchEngine",
            "path": "assets/skills/code_tools/scripts/smart_ast_search/",
        },
    )

    assert "SEARCH:" in result
    assert "SmartSearchEngine" in result
    assert "L" in result  # Line number present

    # 3. Verify Intent-based Search (Semantic)
    result_intent = await kernel.execute_tool(
        "code_tools.smart_ast_search",
        {"query": "classes", "path": "assets/skills/code_tools/scripts/smart_ast_search/"},
    )
    assert "class SmartSearchEngine" in result_intent


@pytest.mark.asyncio
async def test_modular_relative_imports_integration(kernel):
    """Verify that relative imports work correctly in the actual skill directory."""

    # Execute the search tool which relies on 'from .engine import ...'
    # If the relative import failed, this tool call would raise an exception
    try:
        await kernel.execute_tool(
            "code_tools.smart_ast_search",
            {"query": "decorators", "path": "assets/skills/code_tools/scripts/smart_ast_search/"},
        )
    except Exception as e:
        pytest.fail(f"Tool execution failed due to modular import error: {e}")
