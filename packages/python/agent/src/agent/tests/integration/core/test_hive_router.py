"""
src/agent/tests/test_hive_router.py
Test suite for the Hive Agent Router (Phase 14).

Tests for:
1. AgentRoute model
2. HiveRouter routing decisions
3. Keyword-based routing
4. Semantic routing (mocked)
5. Task brief creation
6. Cache behavior

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_hive_router.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.router import HiveRouter, AgentRoute, get_hive_router


class TestAgentRoute:
    """Tests for AgentRoute model."""

    def test_agent_route_creation(self):
        """Test basic AgentRoute creation."""
        route = AgentRoute(target_agent="coder", confidence=0.85, reasoning="Test reasoning")

        assert route.target_agent == "coder"
        assert route.confidence == 0.85
        assert route.reasoning == "Test reasoning"

    def test_agent_route_default_confidence(self):
        """Test AgentRoute with default confidence."""
        route = AgentRoute(target_agent="reviewer", reasoning="Default confidence")

        assert route.confidence is not None

    def test_agent_route_equality(self):
        """Test AgentRoute equality comparison."""
        route1 = AgentRoute(target_agent="coder", confidence=0.75, reasoning="Test")
        route2 = AgentRoute(target_agent="coder", confidence=0.75, reasoning="Test")

        assert route1.target_agent == route2.target_agent
        assert route1.confidence == route2.confidence


class TestHiveRouter:
    """Tests for HiveRouter routing logic."""

    @pytest.fixture
    def router(self):
        """Create a fresh HiveRouter without cortex."""
        r = HiveRouter(semantic_cortex=None)
        r._cache.clear()  # Clear cache from previous tests
        return r

    def test_router_initialization(self, router):
        """Test router initializes with correct defaults."""
        assert router.cortex is None
        assert router._cache == {}

    def test_router_has_personas(self, router):
        """Test router has agent personas defined."""
        assert "coder" in router.AGENT_PERSONAS
        assert "reviewer" in router.AGENT_PERSONAS
        assert "orchestrator" in router.AGENT_PERSONAS

    def test_coder_persona(self, router):
        """Test coder persona definition."""
        persona = router.AGENT_PERSONAS["coder"]

        assert "write" in persona["keywords"]
        assert "implement" in persona["keywords"]
        assert "filesystem" in persona["skills"]

    def test_reviewer_persona(self, router):
        """Test reviewer persona definition."""
        persona = router.AGENT_PERSONAS["reviewer"]

        assert "review" in persona["keywords"]
        assert "test" in persona["keywords"]
        assert "git" in persona["skills"]

    def test_orchestrator_persona(self, router):
        """Test orchestrator persona definition."""
        persona = router.AGENT_PERSONAS["orchestrator"]

        assert "plan" in persona["keywords"]
        assert "explain" in persona["keywords"]
        assert "context" in persona["skills"]


class TestHiveRouterKeywordRouting:
    """Tests for keyword-based routing."""

    @pytest.fixture
    def router(self):
        return HiveRouter(semantic_cortex=None)

    @pytest.mark.asyncio
    async def test_route_coding_task_write(self, router):
        """Test routing 'write code' task to coder."""
        route = await router.route_to_agent("Please write a new function")
        assert route.target_agent == "coder"
        assert "Coding task" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_coding_task_implement(self, router):
        """Test routing 'implement' task to coder."""
        route = await router.route_to_agent("Implement OAuth login")
        assert route.target_agent == "coder"
        assert "Coding task" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_coding_task_refactor(self, router):
        """Test routing 'refactor' task to coder."""
        route = await router.route_to_agent("Refactor the login module")
        assert route.target_agent == "coder"
        assert "Coding task" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_review_task_commit(self, router):
        """Test routing 'commit' task to reviewer."""
        route = await router.route_to_agent("Commit the changes")
        assert route.target_agent == "reviewer"
        assert "QA/Git" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_review_task_test(self, router):
        """Test routing 'test' task to reviewer."""
        route = await router.route_to_agent("Run the tests")
        assert route.target_agent == "reviewer"
        assert "QA/Git" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_review_task_git(self, router):
        """Test routing 'git status' task to reviewer."""
        route = await router.route_to_agent("Show git status")
        assert route.target_agent == "reviewer"
        assert "QA/Git" in route.reasoning

    @pytest.mark.asyncio
    async def test_route_planning_task(self, router):
        """Test routing general/planning task to orchestrator."""
        route = await router.route_to_agent("What is the plan for phase 15?")
        assert route.target_agent == "orchestrator"
        assert "No specific keywords" in route.reasoning or "planning" in route.reasoning.lower()

    @pytest.mark.asyncio
    async def test_route_help_task(self, router):
        """Test routing help task to orchestrator."""
        route = await router.route_to_agent("Help me understand the architecture")
        assert route.target_agent == "orchestrator"


class TestHiveRouterSemanticRouting:
    """Tests for semantic routing with mocked cortex."""

    @pytest.fixture
    def mock_cortex(self):
        """Create a mock SemanticCortex."""
        cortex = MagicMock()
        cortex.recall = AsyncMock(return_value=None)
        return cortex

    @pytest.fixture
    def router_with_cortex(self, mock_cortex):
        """Create router with mocked cortex (sets cortex on singleton)."""
        router = HiveRouter(semantic_cortex=mock_cortex)
        # Set cortex directly on the singleton instance (bypasses singleton init check)
        router.cortex = mock_cortex
        return router

    @pytest.mark.asyncio
    async def test_semantic_routing_no_match(self, router_with_cortex, mock_cortex):
        """Test semantic routing falls back when no cortex match."""
        mock_cortex.recall = AsyncMock(return_value=None)

        route = await router_with_cortex.route_to_agent("random query")

        # Should fall back to keyword routing
        assert route.target_agent in ["coder", "reviewer", "orchestrator"]
        mock_cortex.recall.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_routing_with_match(self, router_with_cortex, mock_cortex):
        """Test semantic routing uses cortex match when available."""
        # Mock a cached result pointing to coder
        cached = MagicMock()
        cached.selected_skills = ["filesystem", "software_engineering"]
        cached.confidence = 0.9
        mock_cortex.recall = AsyncMock(return_value=cached)

        route = await router_with_cortex.route_to_agent("similar query")

        # Should use semantic match with higher confidence
        assert route.target_agent == "coder"
        assert "Semantic match" in route.reasoning

    @pytest.mark.asyncio
    async def test_semantic_routing_git_skills(self, router_with_cortex, mock_cortex):
        """Test semantic routing to reviewer when git skills detected."""
        cached = MagicMock()
        cached.selected_skills = ["git", "testing"]
        cached.confidence = 0.85
        mock_cortex.recall = AsyncMock(return_value=cached)

        route = await router_with_cortex.route_to_agent("git operations")

        assert route.target_agent == "reviewer"


class TestHiveRouterCache:
    """Tests for routing cache behavior."""

    @pytest.fixture
    def router(self):
        return HiveRouter(semantic_cortex=None)

    @pytest.mark.asyncio
    async def test_cache_hit(self, router):
        """Test that cached routes are returned."""
        # First call
        route1 = await router.route_to_agent("test query")
        # Second call (should hit cache)
        route2 = await router.route_to_agent("test query")

        assert route1.target_agent == route2.target_agent

    @pytest.mark.asyncio
    async def test_clear_cache(self, router):
        """Test cache clearing."""
        # Populate cache
        await router.route_to_agent("test")

        assert len(router._cache) > 0

        # Clear
        router.clear_cache()

        assert router._cache == {}


class TestHiveRouterTaskBrief:
    """Tests for TaskBrief creation."""

    @pytest.fixture
    def router(self):
        return HiveRouter(semantic_cortex=None)

    def test_create_task_brief_basic(self, router):
        """Test creating basic task brief."""
        brief = router.create_task_brief(query="Write a login function", target_agent="coder")

        assert brief["task_description"] == "Write a login function"
        assert brief["target_agent"] == "coder"
        assert "filesystem" in brief["allowed_skills"]

    def test_create_task_brief_with_context(self, router):
        """Test creating task brief with additional context."""
        context = {"relevant_files": ["auth.py", "login.py"]}
        brief = router.create_task_brief(
            query="Fix the bug in auth.py", target_agent="coder", context=context
        )

        assert "auth.py" in brief["relevant_files"]
        assert "login.py" in brief["relevant_files"]

    def test_create_task_brief_reviewer(self, router):
        """Test creating task brief for reviewer."""
        brief = router.create_task_brief(query="Run tests and commit", target_agent="reviewer")

        assert brief["target_agent"] == "reviewer"
        assert "git" in brief["allowed_skills"]
        assert "testing" in brief["allowed_skills"]


class TestHiveRouterSingleton:
    """Tests for get_hive_router singleton."""

    def test_get_hive_router_returns_instance(self):
        """Test get_hive_router returns a HiveRouter."""
        router = get_hive_router()
        assert isinstance(router, HiveRouter)

    def test_get_hive_router_singleton(self):
        """Test get_hive_router returns same instance."""
        router1 = get_hive_router()
        router2 = get_hive_router()
        assert router1 is router2


class TestHiveRouterEdgeCases:
    """Edge case tests."""

    @pytest.fixture
    def router(self):
        return HiveRouter(semantic_cortex=None)

    @pytest.mark.asyncio
    async def test_empty_query(self, router):
        """Test routing empty query."""
        route = await router.route_to_agent("")
        # Should default to orchestrator for empty/unclear query
        assert route.target_agent in ["orchestrator", "coder", "reviewer"]

    @pytest.mark.asyncio
    async def test_very_long_query(self, router):
        """Test routing very long query."""
        long_query = "write code " * 100
        route = await router.route_to_agent(long_query)
        assert route.target_agent in ["coder", "reviewer", "orchestrator"]

    @pytest.mark.asyncio
    async def test_mixed_keywords(self, router):
        """Test query with mixed keywords (prefer more specific)."""
        # "commit" is more specific to reviewer
        route = await router.route_to_agent("Write tests and commit")
        # Should route to reviewer due to "commit" keyword
        assert route.target_agent == "reviewer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
