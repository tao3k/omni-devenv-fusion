"""Tests for omni.core.router.main module (OmniRouter)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.core.router.main import OmniRouter, RouterRegistry, get_router
from omni.core.router.router import RouteResult


class TestOmniRouter:
    """Test OmniRouter class."""

    def test_init(self):
        """Test initialization."""
        router = OmniRouter()

        assert router._indexer is not None
        assert router._semantic is not None
        assert router._hive is not None
        assert router._sniffer is not None
        assert router._initialized is False

    def test_component_access(self):
        """Test component property access."""
        router = OmniRouter()

        assert router.indexer is router._indexer
        assert router.semantic is router._semantic
        assert router.hive is router._hive
        assert router.sniffer is router._sniffer

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization with skills."""
        router = OmniRouter()

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [
                    {"name": "status", "description": "Show status"},
                ],
            }
        ]

        await router.initialize(skills)

        assert router._initialized is True

    @pytest.mark.asyncio
    async def test_route_not_initialized(self):
        """Test routing when not initialized falls back to hive."""
        router = OmniRouter()

        # Mock the hive route
        router._hive.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=1.0,
                confidence="high",
            )
        )

        result = await router.route("git.status")

        assert result is not None
        router._hive.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_initialized(self):
        """Test routing when initialized."""
        router = OmniRouter()
        router._initialized = True

        router._hive.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=0.85,
                confidence="high",
            )
        )

        result = await router.route("what's the status")

        assert result is not None
        assert result.skill_name == "git"

    @pytest.mark.asyncio
    async def test_route_with_context(self):
        """Test routing with context."""
        router = OmniRouter()
        router._initialized = True

        router._hive.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="commit",
                score=0.7,
                confidence="medium",
            )
        )

        result = await router.route("commit this", context={"cwd": "/test"})

        assert result is not None
        router._hive.route.assert_called_once_with("commit this", {"cwd": "/test"})

    @pytest.mark.asyncio
    async def test_suggest_skills(self):
        """Test skill suggestions."""
        router = OmniRouter()

        with patch.object(router._sniffer, "sniff", return_value=["git", "python_engineering"]):
            suggestions = await router.suggest_skills("/tmp/test")

        assert "git" in suggestions
        assert "python_engineering" in suggestions

    def test_is_ready(self):
        """Test is_ready property."""
        router = OmniRouter()
        router._initialized = True
        # is_ready is a property, so we mock the underlying _store
        router._indexer._store = MagicMock()

        assert router.is_ready() is True

        router._indexer._store = None
        assert router.is_ready() is False

    def test_get_stats(self):
        """Test get_stats method."""
        router = OmniRouter()
        router._initialized = True

        stats = router.get_stats()

        assert "initialized" in stats
        assert "indexer_stats" in stats
        assert "is_ready" in stats
        assert stats["initialized"] is True


class TestRouterRegistry:
    """Test RouterRegistry class."""

    def setup_method(self):
        """Clean up registry before each test."""
        RouterRegistry._instances.clear()
        RouterRegistry._default = "default"

    def teardown_method(self):
        """Clean up registry after each test."""
        RouterRegistry._instances.clear()
        RouterRegistry._default = "default"

    def test_get_creates_instance(self):
        """Test that get creates a new instance."""
        router = RouterRegistry.get()

        assert router is not None
        assert isinstance(router, OmniRouter)

    def test_get_returns_same_instance(self):
        """Test that get returns the same instance."""
        router1 = RouterRegistry.get()
        router2 = RouterRegistry.get()

        assert router1 is router2

    def test_get_named_instance(self):
        """Test getting a named instance."""
        router1 = RouterRegistry.get("router1")
        router2 = RouterRegistry.get("router1")
        router3 = RouterRegistry.get("router2")

        assert router1 is router2
        assert router1 is not router3

    def test_set_default(self):
        """Test setting default router name."""
        RouterRegistry.set_default("my_router")

        assert RouterRegistry._default == "my_router"

    def test_reset(self):
        """Test resetting a router instance."""
        router1 = RouterRegistry.get("test1")
        RouterRegistry.reset("test1")

        router2 = RouterRegistry.get("test1")

        assert router1 is not router2

    def test_reset_all(self):
        """Test resetting all instances."""
        RouterRegistry.get("a")
        RouterRegistry.get("b")

        RouterRegistry.reset_all()

        assert len(RouterRegistry._instances) == 0


class TestGetRouter:
    """Test get_router convenience function."""

    def setup_method(self):
        """Clean up registry."""
        RouterRegistry._instances.clear()
        RouterRegistry._default = "default"

    def teardown_method(self):
        """Clean up registry."""
        RouterRegistry._instances.clear()
        RouterRegistry._default = "default"

    def test_get_router(self):
        """Test get_router function."""
        router = get_router()

        assert router is not None
        assert isinstance(router, OmniRouter)

    def test_get_router_named(self):
        """Test get_router with name."""
        router = get_router("special")

        assert router is not None
        assert "special" in RouterRegistry._instances
