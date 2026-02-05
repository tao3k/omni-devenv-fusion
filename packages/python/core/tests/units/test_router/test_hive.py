"""Tests for omni.core.router.hive module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from omni.core.router.hive import HiveRouter, MultiHiveRouter
from omni.core.router.router import RouteResult


class TestHiveRouter:
    """Test HiveRouter class."""

    def test_init_with_semantic_router(self):
        """Test initialization with semantic router."""
        mock_semantic = MagicMock()
        hive = HiveRouter(mock_semantic)

        assert hive._semantic is mock_semantic
        assert hive._fallback is not None

    @pytest.mark.asyncio
    async def test_route_explicit_command(self):
        """Test routing explicit command pattern."""
        mock_semantic = MagicMock()
        mock_semantic.route = AsyncMock(return_value=None)

        hive = HiveRouter(mock_semantic)
        result = await hive.route("git.status")

        assert result is not None
        assert result.skill_name == "git"
        assert result.command_name == "status"
        assert result.score == 1.0
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_route_explicit_command_memory_save(self):
        """Test routing explicit memory.save command."""
        mock_semantic = MagicMock()
        mock_semantic.route = AsyncMock(return_value=None)

        hive = HiveRouter(mock_semantic)
        result = await hive.route("memory.save")

        assert result is not None
        assert result.skill_name == "memory"
        assert result.command_name == "save"

    @pytest.mark.asyncio
    async def test_route_falls_back_to_semantic(self):
        """Test that routing falls back to semantic when no explicit match."""
        mock_semantic = MagicMock()
        mock_semantic.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="commit",
                score=0.85,
                confidence="high",
            )
        )

        hive = HiveRouter(mock_semantic)
        result = await hive.route("commit the changes")

        assert result is not None
        assert result.skill_name == "git"
        mock_semantic.route.assert_called_once_with("commit the changes")

    @pytest.mark.asyncio
    async def test_route_returns_none_when_both_fail(self):
        """Test that routing returns None when both explicit and semantic fail."""
        mock_semantic = MagicMock()
        mock_semantic.route = AsyncMock(return_value=None)

        hive = HiveRouter(mock_semantic)
        result = await hive.route("some random query that doesn't match")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_empty_query(self):
        """Test that empty query returns None."""
        mock_semantic = MagicMock()

        hive = HiveRouter(mock_semantic)
        result = await hive.route("")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_context_git_repo(self):
        """Test context-aware routing for git repo."""
        mock_semantic = MagicMock()
        mock_semantic.route = AsyncMock(return_value=None)

        hive = HiveRouter(mock_semantic)
        result = await hive.route("commit this", context={"cwd": "/fake/repo"})

        # Should not match because "commit this" doesn't contain commit keywords strongly
        assert result is None

    def test_is_ready(self):
        """Test is_ready property."""
        mock_semantic = MagicMock()
        mock_semantic.is_ready.return_value = True

        hive = HiveRouter(mock_semantic)
        assert hive.is_ready is True

        mock_semantic.is_ready.return_value = False
        assert hive.is_ready is False


class TestMultiHiveRouter:
    """Test MultiHiveRouter class."""

    def test_init(self):
        """Test initialization."""
        multi = MultiHiveRouter()

        assert multi._hives == {}
        assert multi._default_hive is None

    def test_register_hive(self):
        """Test registering a hive."""
        multi = MultiHiveRouter()
        hive = MagicMock()

        multi.register_hive("python", hive)

        assert "python" in multi._hives
        assert multi._hives["python"] is hive

    def test_set_default_hive(self):
        """Test setting default hive."""
        multi = MultiHiveRouter()
        hive = MagicMock()

        multi.set_default_hive(hive)

        assert multi._default_hive is hive

    @pytest.mark.asyncio
    async def test_route_to_specific_hive(self):
        """Test routing to a specific domain hive."""
        multi = MultiHiveRouter()

        hive = MagicMock()
        hive.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=0.9,
                confidence="high",
            )
        )
        multi.register_hive("git_ops", hive)

        result = await multi.route("git status", domain="git_ops")

        assert result is not None
        assert result.skill_name == "git"
        hive.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_falls_back_to_default(self):
        """Test routing falls back to default when domain not found."""
        multi = MultiHiveRouter()

        default_hive = MagicMock()
        default_hive.route = AsyncMock(
            return_value=RouteResult(
                skill_name="python",
                command_name="test",
                score=0.8,
                confidence="high",
            )
        )
        multi.set_default_hive(default_hive)

        result = await multi.route("run tests", domain="unknown_domain")

        assert result is not None
        default_hive.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_returns_none_when_no_hive(self):
        """Test routing returns None when no hive available."""
        multi = MultiHiveRouter()

        result = await multi.route("test query")

        assert result is None
