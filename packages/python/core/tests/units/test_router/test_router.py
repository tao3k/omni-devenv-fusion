"""Tests for omni.core.router.router module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from omni.core.router.router import (
    FallbackRouter,
    RouteResult,
    SemanticRouter,
    UnifiedRouter,
)


class TestRouteResult:
    """Test RouteResult dataclass."""

    def test_create_route_result(self):
        """Test creating a RouteResult."""
        result = RouteResult(
            skill_name="git",
            command_name="commit",
            score=0.85,
            confidence="high",
        )

        assert result.skill_name == "git"
        assert result.command_name == "commit"
        assert result.score == 0.85
        assert result.confidence == "high"


class TestFallbackRouter:
    """Test FallbackRouter for explicit command matching."""

    @pytest.mark.asyncio
    async def test_match_explicit_command(self):
        """Test matching explicit command pattern."""
        router = FallbackRouter()

        result = await router.route("git.status")

        assert result is not None
        assert result.skill_name == "git"
        assert result.command_name == "status"
        assert result.score == 1.0
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_match_memory_save(self):
        """Test matching memory.save command."""
        router = FallbackRouter()

        result = await router.route("memory.save")

        assert result is not None
        assert result.skill_name == "memory"
        assert result.command_name == "save"

    @pytest.mark.asyncio
    async def test_no_match_natural_language(self):
        """Test that natural language doesn't match."""
        router = FallbackRouter()

        result = await router.route("帮我保存代码")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_empty(self):
        """Test that empty query doesn't match."""
        router = FallbackRouter()

        result = await router.route("")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_single_word(self):
        """Test that single word doesn't match."""
        router = FallbackRouter()

        result = await router.route("status")

        assert result is None


class TestSemanticRouter:
    """Test SemanticRouter for semantic matching."""

    def test_init_with_indexer(self):
        """Test initialization with indexer."""
        mock_indexer = MagicMock()
        router = SemanticRouter(mock_indexer)

        assert router._indexer is mock_indexer

    @pytest.mark.asyncio
    async def test_route_returns_none_on_no_results(self):
        """Test routing returns None when no results."""
        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(return_value=[])

        router = SemanticRouter(mock_indexer)
        result = await router.route("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_returns_result_on_match(self):
        """Test routing returns result on match."""
        from omni.foundation.bridge import SearchResult

        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                SearchResult(
                    id="test",
                    score=0.85,
                    payload={
                        "type": "command",
                        "skill_name": "git",
                        "command": "status",
                        "weight": 2.0,
                    },
                )
            ]
        )

        router = SemanticRouter(mock_indexer)
        result = await router.route("what's the status")

        assert result is not None
        assert result.skill_name == "git"
        assert result.command_name == "status"
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_route_filters_by_threshold(self):
        """Test routing filters results below threshold."""
        from omni.foundation.bridge import SearchResult

        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                SearchResult(
                    id="test",
                    score=0.30,  # Below threshold
                    payload={
                        "type": "command",
                        "skill_name": "git",
                        "command": "status",
                        "weight": 2.0,
                    },
                )
            ]
        )

        router = SemanticRouter(mock_indexer)
        result = await router.route("some query", threshold=0.5)

        assert result is None

    @pytest.mark.asyncio
    async def test_route_ignores_non_command_results(self):
        """Test routing ignores skill-level (non-command) results."""
        from omni.foundation.bridge import SearchResult

        mock_indexer = MagicMock()
        mock_indexer.search = AsyncMock(
            return_value=[
                SearchResult(
                    id="test",
                    score=0.90,
                    payload={
                        "type": "skill",  # Not a command
                        "skill_name": "git",
                        "weight": 1.0,
                    },
                )
            ]
        )

        router = SemanticRouter(mock_indexer)
        result = await router.route("test query")

        assert result is None

    def test_get_confidence_high(self):
        """Test confidence level for high scores."""
        router = SemanticRouter(MagicMock())

        assert router._get_confidence(0.90) == "high"
        assert router._get_confidence(0.80) == "high"

    def test_get_confidence_medium(self):
        """Test confidence level for medium scores."""
        router = SemanticRouter(MagicMock())

        assert router._get_confidence(0.65) == "medium"
        assert router._get_confidence(0.55) == "medium"

    def test_get_confidence_low(self):
        """Test confidence level for low scores."""
        router = SemanticRouter(MagicMock())

        assert router._get_confidence(0.45) == "low"
        assert router._get_confidence(0.30) == "low"

    def test_is_ready(self):
        """Test is_ready check."""
        mock_indexer = MagicMock()
        mock_indexer.is_ready = True

        router = SemanticRouter(mock_indexer)
        assert router.is_ready() is True

        mock_indexer.is_ready = False
        assert router.is_ready() is False


class TestUnifiedRouter:
    """Test UnifiedRouter combining semantic and fallback routing."""

    @pytest.mark.asyncio
    async def test_semantic_routing_first(self):
        """Test that semantic routing is tried first."""
        semantic = MagicMock()
        semantic.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=0.85,
                confidence="high",
            )
        )
        fallback = MagicMock()
        fallback.route = AsyncMock(return_value=None)

        router = UnifiedRouter(semantic, fallback)
        result = await router.route("what's the status")

        assert result is not None
        assert result.skill_name == "git"
        semantic.route.assert_called_once()
        fallback.route.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_on_semantic_miss(self):
        """Test fallback when semantic routing fails."""
        semantic = MagicMock()
        semantic.route = AsyncMock(return_value=None)
        fallback = MagicMock()
        fallback.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=1.0,
                confidence="high",
            )
        )

        router = UnifiedRouter(semantic, fallback)
        result = await router.route("git.status")

        assert result is not None
        assert result.skill_name == "git"
        semantic.route.assert_called_once()
        fallback.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_both_fail(self):
        """Test that None is returned when both routers fail."""
        semantic = MagicMock()
        semantic.route = AsyncMock(return_value=None)
        fallback = MagicMock()
        fallback.route = AsyncMock(return_value=None)

        router = UnifiedRouter(semantic, fallback)
        result = await router.route("some random query that doesn't match anything")

        assert result is None

    @pytest.mark.asyncio
    async def test_route_with_threshold(self):
        """Test routing with custom threshold."""
        semantic = MagicMock()
        semantic.route = AsyncMock(
            return_value=RouteResult(
                skill_name="git",
                command_name="status",
                score=0.65,
                confidence="medium",
            )
        )
        fallback = MagicMock()
        fallback.route = AsyncMock(return_value=None)

        router = UnifiedRouter(semantic, fallback)
        result = await router.route("test query", 0.7)

        # Should pass threshold through
        semantic.route.assert_called_once_with("test query", 0.7)
        # Fallback should be called because semantic confidence is medium
        fallback.route.assert_called_once_with("test query")
