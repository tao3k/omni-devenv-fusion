"""
Unit tests for Alias/Override awareness in OmniLoop
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from omni.agent.core.omni.loop import OmniLoop
from omni.agent.core.omni.config import OmniLoopConfig
from omni.core.config.loader import CommandOverride, OverridesConfig


@pytest.fixture
def mock_kernel():
    kernel = MagicMock()
    kernel.skill_context = MagicMock()
    # Mock some core commands
    kernel.skill_context.get_core_commands.return_value = [
        "crawl4ai.crawl_url",
        "memory.save_memory",
    ]
    # Mock command objects
    cmd1 = MagicMock()
    cmd1.description = "Original crawl description"
    cmd2 = MagicMock()
    cmd2.description = "Original memory description"

    kernel.skill_context.get_command.side_effect = lambda name: {
        "crawl4ai.crawl_url": cmd1,
        "memory.save_memory": cmd2,
    }.get(name)

    kernel.execute_tool = AsyncMock(return_value="success")
    return kernel


@pytest.mark.asyncio
async def test_adaptive_projection_applies_aliases(mock_kernel):
    """Verify that tool schemas projected to LLM use aliases from config."""
    config = OmniLoopConfig()
    loop = OmniLoop(config=config, kernel=mock_kernel)

    # Mock the overrides config
    mock_overrides = OverridesConfig(
        commands={
            "crawl4ai.crawl_url": CommandOverride(alias="web_fetch", append_doc="USE THIS!"),
            "memory.save_memory": CommandOverride(alias="remember", append_doc="SAVE THIS!"),
        }
    )

    # We need to patch the extraction and cache logic
    with (
        patch("omni.core.config.loader.load_command_overrides", return_value=mock_overrides),
        patch("omni.core.cache.tool_schema.get_cached_schema") as mock_get_schema,
    ):
        # Mock what extract_tool_schemas would return
        mock_get_schema.side_effect = [
            {"name": "crawl4ai.crawl_url", "description": "Original crawl description"},
            {"name": "memory.save_memory", "description": "Original memory description"},
        ]

        schemas = await loop._get_adaptive_tool_schemas()

        # Verify Aliases applied
        names = [s["name"] for s in schemas]
        assert "web_fetch" in names
        assert "remember" in names
        assert "crawl4ai.crawl_url" not in names

        # Verify Documentation appended
        web_fetch_schema = next(s for s in schemas if s["name"] == "web_fetch")
        assert "USE THIS!" in web_fetch_schema["description"]


@pytest.mark.asyncio
async def test_execute_tool_proxy_resolves_aliases(mock_kernel):
    """Verify that tool execution resolves aliases back to canonical names."""
    config = OmniLoopConfig()
    loop = OmniLoop(config=config, kernel=mock_kernel)

    # Mock the resolve_alias function
    with patch("omni.core.config.loader.resolve_alias") as mock_resolve:
        mock_resolve.side_effect = lambda alias: {"web_fetch": "crawl4ai.crawl_url"}.get(alias)

        # Call proxy with alias
        await loop._execute_tool_proxy("web_fetch", {"url": "test.com"})

        # Verify kernel received CANONICAL name
        mock_kernel.execute_tool.assert_called_once_with(
            "crawl4ai.crawl_url", {"url": "test.com"}, caller=None
        )


@pytest.mark.asyncio
async def test_execute_tool_proxy_handles_non_aliases(mock_kernel):
    """Verify that non-aliased tools still work correctly."""
    config = OmniLoopConfig()
    loop = OmniLoop(config=config, kernel=mock_kernel)

    with patch("omni.core.config.loader.resolve_alias", return_value=None):
        await loop._execute_tool_proxy("git.status", {})

        mock_kernel.execute_tool.assert_called_once_with("git.status", {}, caller=None)
