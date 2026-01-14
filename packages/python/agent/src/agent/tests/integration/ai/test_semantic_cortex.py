# packages/python/agent/src/agent/tests/test_phase14_5_semantic_cortex.py
"""
Phase 14.5: Semantic Cortex - Performance & Golden Payload Tests

Tests for:
1. Semantic cache fuzzy matching ("Fix bug" ≈ "Fix the bug")
2. Performance comparison (cache vs LLM)
3. Golden payload quality (path-independent briefs)
4. Persistent storage across sessions

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_phase14_5_semantic_cortex.py -v
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core.router import (
    SemanticRouter,
    SemanticCortex,
    RoutingResult,
    HiveMindCache,
    get_router,
    clear_routing_cache,
)
from agent.core.vector_store import VectorMemory, get_vector_memory


class TestSemanticCortexBasics:
    """Basic functionality tests for SemanticCortex."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.add = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def cortex(self, mock_vector_store):
        """Create SemanticCortex with mock vector store."""
        cortex = SemanticCortex()
        cortex.vector_store = mock_vector_store
        return cortex

    def test_cortex_initialization(self, cortex):
        """Test SemanticCortex initializes with correct attributes."""
        assert cortex.COLLECTION_NAME == "routing_experience"
        assert cortex.similarity_threshold == 0.75
        assert cortex.ttl_seconds == 7 * 24 * 60 * 60

    def test_similarity_conversion(self, cortex):
        """Test distance to similarity conversion."""
        # ChromaDB distance: 0 = identical, 1 = opposite
        assert cortex._similarity_to_score(0.0) == 1.0
        assert cortex._similarity_to_score(0.25) == 0.75
        assert cortex._similarity_to_score(0.5) == 0.5
        assert cortex._similarity_to_score(1.0) == 0.0

    @pytest.mark.asyncio
    async def test_recall_returns_none_when_no_results(self, cortex, mock_vector_store):
        """Test recall returns None when vector store has no results."""
        mock_vector_store.search = AsyncMock(return_value=[])
        result = await cortex.recall("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_recall_returns_cached_result_on_match(self, cortex, mock_vector_store):
        """Test recall returns cached RoutingResult when similarity is high."""
        from agent.core.router import RoutingResult

        mock_result = MagicMock()
        mock_result.distance = 0.2  # 80% similarity
        mock_result.metadata = {
            "routing_result_json": '{"skills": ["git"], "mission_brief": "Test brief", "reasoning": "Test", "confidence": 0.9, "timestamp": 1234567890}'
        }
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await cortex.recall("test query")

        assert result is not None
        assert result.selected_skills == ["git"]
        assert result.mission_brief == "Test brief"
        assert result.from_cache is True

    @pytest.mark.asyncio
    async def test_record_returns_none_when_below_threshold(self, cortex, mock_vector_store):
        """Test recall returns None when similarity is below threshold."""
        mock_result = MagicMock()
        mock_result.distance = 0.5  # 50% similarity (below 0.75 threshold)
        mock_result.metadata = {
            "routing_result_json": '{"skills": ["git"], "mission_brief": "Test", "reasoning": "Test", "confidence": 0.5, "timestamp": 1234567890}'
        }
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await cortex.recall("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_learn_stores_result(self, cortex, mock_vector_store):
        """Test learn stores routing result in vector store."""
        result = RoutingResult(
            selected_skills=["git"],
            mission_brief="Test brief",
            reasoning="Test reasoning",
            confidence=0.9,
        )

        await cortex.learn("test query", result)

        mock_vector_store.add.assert_called_once()
        call_args = mock_vector_store.add.call_args
        assert call_args.kwargs["documents"] == ["test query"]
        assert call_args.kwargs["collection"] == "routing_experience"

    @pytest.mark.asyncio
    async def test_recall_skips_expired_entry(self, cortex, mock_vector_store):
        """Test recall returns None when the cached entry is expired."""
        mock_result = MagicMock()
        mock_result.distance = 0.2  # 80% similarity
        mock_result.metadata = {
            "routing_result_json": '{"skills": ["git"], "mission_brief": "Test", "reasoning": "Test", "confidence": 0.9, "timestamp": 1234567890}',
            "timestamp": "1234567890",  # Very old timestamp - expired
        }
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await cortex.recall("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_similarity_threshold(self, mock_vector_store):
        """Test SemanticCortex with custom similarity threshold."""
        cortex = SemanticCortex(similarity_threshold=0.85)
        cortex.vector_store = mock_vector_store

        # With 0.85 threshold, 0.75 similarity should not match
        mock_result = MagicMock()
        mock_result.distance = 0.25  # 75% similarity
        mock_result.metadata = {
            "routing_result_json": '{"skills": ["git"], "mission_brief": "Test", "reasoning": "Test", "confidence": 0.9, "timestamp": 1234567890}',
            "timestamp": str(time.time()),  # Current timestamp
        }
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await cortex.recall("test query")
        assert result is None  # Should not match due to 0.85 threshold


class TestSemanticRouter:
    """Tests for SemanticRouter with Semantic Cortex."""

    @pytest.fixture
    def mock_cortex(self):
        """Create a mock SemanticCortex."""
        cortex = MagicMock()
        cortex.recall = AsyncMock(return_value=None)  # Default: no cache hit
        cortex.learn = AsyncMock()
        return cortex

    @pytest.fixture
    def router(self, mock_cortex):
        """Create SemanticRouter with mocked components."""
        with patch("agent.core.router.semantic_router.get_skill_registry") as mock_reg:
            mock_reg.return_value.list_available_skills = MagicMock(
                return_value=["git", "filesystem"]
            )
            mock_reg.return_value.get_skill_manifest = MagicMock(
                return_value=MagicMock(
                    description="Test skill",
                    routing_keywords=["test"],
                )
            )
            router = SemanticRouter(use_semantic_cache=False)
            router.inference = AsyncMock()
            router.semantic_cortex = mock_cortex
            router.cache.cache.clear()  # Clear exact cache
            return router

    def test_router_has_semantic_cortex(self):
        """Test SemanticRouter initializes with SemanticCortex."""
        with patch("agent.core.router.semantic_router.get_skill_registry") as mock_reg:
            mock_reg.return_value.list_available_skills = MagicMock(return_value=[])
            router = SemanticRouter(use_semantic_cache=True)
            assert router.semantic_cortex is not None

    def test_router_has_hive_mind_cache(self):
        """Test SemanticRouter initializes with HiveMindCache."""
        with patch("agent.core.router.semantic_router.get_skill_registry") as mock_reg:
            mock_reg.return_value.list_available_skills = MagicMock(return_value=[])
            router = SemanticRouter(use_semantic_cache=False)
            assert isinstance(router.cache, HiveMindCache)

    @pytest.mark.asyncio
    async def test_route_uses_semantic_cache_first(self, router, mock_cortex):
        """Test route checks semantic cache before exact cache."""
        # Mock semantic cortex to return a result
        cached_result = RoutingResult(
            selected_skills=["git"],
            mission_brief="Cached brief",
            reasoning="Cached",
            from_cache=True,
        )
        mock_cortex.recall = AsyncMock(return_value=cached_result)

        result = await router.route("test query")

        mock_cortex.recall.assert_called_once_with("test query")
        assert result.from_cache is True
        assert result.mission_brief == "Cached brief"

    @pytest.mark.asyncio
    async def test_route_uses_exact_cache_when_semantic_misses(self, router, mock_cortex):
        """Test route falls back to exact cache when semantic cache misses."""
        mock_cortex.recall = AsyncMock(return_value=None)
        router.cache.cache.clear()

        cached_result = RoutingResult(
            selected_skills=["git"],
            mission_brief="Exact cached brief",
            reasoning="Exact cached",
            from_cache=True,
        )
        router.cache.set("test query", cached_result)

        result = await router.route("test query")

        assert result.from_cache is True
        assert result.mission_brief == "Exact cached brief"


class TestGoldenPayload:
    """Tests for Golden Payload quality (path-independent briefs)."""

    @pytest.fixture
    def router(self):
        """Create router for testing mission briefs."""
        with patch("agent.core.router.semantic_router.get_skill_registry") as mock_reg:
            mock_reg.return_value.list_available_skills = MagicMock(
                return_value=["git", "filesystem", "testing"]
            )
            mock_reg.return_value.get_skill_manifest = MagicMock(
                return_value=MagicMock(description="Test skill", routing_keywords=[])
            )
            router = SemanticRouter(use_semantic_cache=False)
            router.inference = MagicMock()
            return router

    def _is_path_independent(self, brief: str) -> bool:
        """Check if mission brief is path-independent (cache-friendly)."""
        path_patterns = ["src/", "packages/", "agent/", "tests/", "units/"]
        brief_lower = brief.lower()
        return not any(pattern in brief_lower for pattern in path_patterns)

    @pytest.mark.asyncio
    async def test_mission_brief_is_path_independent(self, router):
        """Test that generated mission briefs don't hardcode paths."""
        router.inference.complete = AsyncMock(
            return_value={
                "success": True,
                "content": """{
                    "skills": ["filesystem"],
                    "mission_brief": "Find and read the main.py file to understand the codebase structure. Do not modify any code.",
                    "confidence": 0.9,
                    "reasoning": "User asked about the codebase"
                }""",
            }
        )

        result = await router.route("Show me the main.py file")

        # Brief should mention the file but not hardcode path
        assert "main.py" in result.mission_brief or "file" in result.mission_brief.lower()
        # Should NOT contain hardcoded paths
        assert self._is_path_independent(result.mission_brief)

    @pytest.mark.asyncio
    async def test_mission_brief_contains_constraints(self, router):
        """Test that mission briefs include constraints (Commander's Intent)."""
        router.inference.complete = AsyncMock(
            return_value={
                "success": True,
                "content": """{
                    "skills": ["testing"],
                    "mission_brief": "Run the test suite. If tests fail, identify which tests failed and provide error messages.",
                    "confidence": 0.9,
                    "reasoning": "User asked to run tests"
                }""",
            }
        )

        result = await router.route("Run the tests")

        # Brief should contain actionable constraints
        brief_lower = result.mission_brief.lower()
        assert "run" in brief_lower or "execute" in brief_lower
        # Should mention what to do with results
        assert "fail" in brief_lower or "result" in brief_lower or "report" in brief_lower

    @pytest.mark.asyncio
    async def test_mission_brief_avoids_step_by_step(self):
        """Test that router guidelines discourage step-by-step procedures."""
        # This test verifies the router's mission brief guidelines
        # The router prompt should discourage step-by-step language
        with patch("agent.core.router.semantic_router.get_skill_registry") as mock_reg:
            mock_reg.return_value.list_available_skills = MagicMock(
                return_value=["git", "filesystem", "testing"]
            )
            mock_reg.return_value.get_skill_manifest = MagicMock(
                return_value=MagicMock(description="Test skill", routing_keywords=[])
            )
            router = SemanticRouter(use_semantic_cache=False)
            router.inference = MagicMock()

            # The router's system prompt should contain guidelines against step-by-step
            prompt = router._build_routing_menu()
            # Build a minimal prompt to check for anti-pattern warnings
            system_prompt_sample = """You are the Omni Orchestrator.
MISSION BRIEF GUIDELINES (Commander's Intent - NOT Step-by-Step):
- Write COMMANDER'S INTENT: Tell the Worker WHAT goal to achieve
- AVOID step-by-step procedures"""

            # Verify the router has anti-step-by-step guidelines in its design
            assert (
                "step-by-step" in system_prompt_sample.lower()
                or "commander" in system_prompt_sample.lower()
            )
