"""Tests for omni.core.router.hybrid_search module - Rust-Native Implementation.

These tests verify the Rust-native hybrid search implementation that delegates
to omni-vector's search_tools for vector search + keyword rescue.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omni.test_kit.fixtures.vector import make_tool_search_payload


def _stub_embed(search) -> None:
    """Inject deterministic async embedding to keep tests hermetic."""
    search._embed_func = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]])


class TestHybridSearchRustNative:
    """Test Rust-native HybridSearch implementation."""

    def test_default_initialization(self):
        """Test default hybrid search initialization (no args required)."""
        # The new HybridSearch doesn't need indexers - it uses Rust internally
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()

        # Verify it has the store reference
        assert search._store is not None

    def test_default_uses_skills_database_path(self):
        """HybridSearch() with no storage_path must use get_vector_db_path().

        Ensures route test and sync/reindex use the same skills store root
        (get_vector_db_path(); get_database_path('skills') is not used for store root).
        """
        from omni.core.router.hybrid_search import HybridSearch

        with (
            patch(
                "omni.foundation.config.dirs.get_vector_db_path",
                return_value=Path("/cache/omni-vector"),
            ) as mock_get_path,
            patch(
                "omni.foundation.bridge.rust_vector.get_vector_store",
            ) as mock_get_store,
        ):
            search = HybridSearch()

        mock_get_path.assert_called_once()
        mock_get_store.assert_called_once_with("/cache/omni-vector")

    def test_fixed_weights(self):
        """Test that weights are fixed (no configurable weights in Rust-native)."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()

        semantic, keyword = search.get_weights()
        # Rust weights: SEMANTIC_WEIGHT=1.0, KEYWORD_WEIGHT=1.5
        assert semantic == 1.0
        assert keyword == 1.5

    def test_stats_shows_rust_implementation(self):
        """Test that stats indicate Rust-native Weighted RRF implementation."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        stats = search.stats()

        assert stats["implementation"] == "rust-native-weighted-rrf"
        assert stats["strategy"] == "weighted_rrf_field_boosting"
        assert stats["semantic_weight"] == 1.0
        assert stats["keyword_weight"] == 1.5
        assert stats["rrf_k"] == 10
        assert stats["field_boosting"]["name_token_boost"] == 0.5
        assert stats["field_boosting"]["exact_phrase_boost"] == 1.5

    def test_set_weights_logs_info(self):
        """Test that set_weights logs info about fixed weights."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        # Should not error, just log info
        search.set_weights(0.9, 0.1)

        # Weights should still be the same (fixed)
        semantic, keyword = search.get_weights()
        assert semantic == 1.0
        assert keyword == 1.5

    def test_get_weights_reads_rust_profile(self):
        """Weights should be sourced from Rust profile, not Python constants."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        search._store.get_search_profile = MagicMock(
            return_value={
                "semantic_weight": 0.9,
                "keyword_weight": 1.7,
                "rrf_k": 20,
                "implementation": "rust-profile-test",
            }
        )
        semantic, keyword = search.get_weights()
        assert semantic == 0.9
        assert keyword == 1.7


class TestHybridSearchWithMockedStore:
    """Test HybridSearch with mocked Rust store."""

    @pytest.mark.asyncio
    async def test_search_calls_rust_store(self):
        """Test that search delegates to Rust store.search_tools."""
        from omni.core.router.hybrid_search import HybridSearch

        # Create mock results that Rust would return
        mock_results = [
            make_tool_search_payload(
                score=0.95,
                final_score=0.97,
                tool_name="commit",
                file_path="git/scripts/commit.py",
                routing_keywords=["commit", "git"],
                input_schema="{}",
            )
        ]

        # Use a store mock without agentic_search so the code path uses search_tools.
        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=mock_results)
        search._store = mock_store

        results = await search.search("git commit")

        # Verify store was called
        search._store.search_tools.assert_called_once()

        # Verify results format (final_score is re-calibrated by Python-side
        # _recalibrate_confidence using the profile formula after all boosts)
        assert len(results) == 1
        assert results[0]["id"] == "git.commit"
        assert results[0]["skill_name"] == "git"
        assert results[0]["command"] == "commit"
        assert results[0]["confidence"] == "high"
        assert results[0]["final_score"] >= 0.90  # high_base floor from profile

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test that limit is passed to Rust store."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        await search.search("test", limit=5)

        # Verify limit was passed (agentic_search path would use same kwargs)
        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("limit") == 5

    @pytest.mark.asyncio
    async def test_search_with_threshold(self):
        """Test that threshold is passed to Rust store."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        await search.search("test", min_score=0.7)

        # Verify threshold was passed
        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("threshold") == 0.7

    @pytest.mark.asyncio
    async def test_search_with_confidence_profile_override(self):
        """Confidence profile override should be forwarded to Rust bridge."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        profile = {
            "high_threshold": 0.81,
            "medium_threshold": 0.55,
            "low_floor": 0.12,
        }
        await search.search("test", confidence_profile=profile)

        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("confidence_profile") == profile

    @pytest.mark.asyncio
    async def test_hybrid_search_always_reranks(self):
        """Hybrid search always passes rerank=True to the store (no override)."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        await search.search("test")

        call_args = search._store.search_tools.call_args
        assert call_args.kwargs.get("rerank") is True

    @pytest.mark.asyncio
    async def test_search_passes_query_for_keyword_rescue(self):
        """Test that query text is passed for keyword rescue."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        await search.search("git commit message")

        # Verify query_text was passed (triggers keyword rescue in Rust)
        call_args = search._store.search_tools.call_args
        assert call_args is not None
        assert "git commit message" in str(call_args)

    @pytest.mark.asyncio
    async def test_search_intent_override_passed_to_agentic(self):
        """When intent_override is set, it is passed to agentic_search instead of rule-based intent."""
        from omni.core.router.hybrid_search import HybridSearch

        mock_results = [
            make_tool_search_payload(
                score=0.9,
                final_score=0.88,
                tool_name="commit",
                skill_name="git",
                file_path="git/scripts/commit.py",
                routing_keywords=["git", "commit"],
                input_schema="{}",
            )
        ]
        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["agentic_search"])
        mock_store.agentic_search = AsyncMock(return_value=mock_results)
        search._store = mock_store

        await search.search("git commit", limit=3, intent_override="semantic")

        mock_store.agentic_search.assert_called_once()
        call_kwargs = mock_store.agentic_search.call_args.kwargs
        assert call_kwargs.get("intent") == "semantic"
        # No concrete URL → rust_limit = limit (no expansion)
        assert call_kwargs.get("limit") == 3

    @pytest.mark.asyncio
    async def test_rust_limit_expanded_when_query_has_concrete_url(self):
        """When query contains concrete URL (https://...), agentic_search receives expanded limit so URL tools (crawl4ai) can enter top-N."""
        from omni.core.router.hybrid_search import HybridSearch

        mock_results = [
            make_tool_search_payload(
                score=0.9,
                tool_name="crawl_url",
                skill_name="crawl4ai",
                file_path="crawl4ai/scripts/crawl.py",
                routing_keywords=["crawl", "url"],
                input_schema='{"properties":{"url":{"type":"string"}}}',
            ),
            make_tool_search_payload(
                score=0.85,
                tool_name="git_repo_analyer",
                skill_name="researcher",
                file_path="researcher/scripts/analyze.py",
                routing_keywords=["research", "analyze"],
                input_schema="{}",
            ),
        ]
        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["agentic_search", "get_search_profile"])
        mock_store.agentic_search = AsyncMock(return_value=mock_results)
        mock_store.get_search_profile = MagicMock(
            return_value={"semantic_weight": 1.0, "keyword_weight": 1.5, "rrf_k": 10}
        )
        search._store = mock_store

        await search.search(
            "help me research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
            limit=10,
            skip_translation=True,
        )

        call_kwargs = mock_store.agentic_search.call_args.kwargs
        # Concrete URL → rust_limit = min(10*20, 200) = 200
        assert call_kwargs.get("limit") == 200


class TestHybridSearchIntegration:
    """Integration tests for Rust-native hybrid search."""

    @pytest.mark.asyncio
    async def test_result_format_complete(self):
        """Test that results have all required fields."""
        from omni.core.router.hybrid_search import HybridSearch

        mock_results = [
            make_tool_search_payload(
                name="python.run",
                description="Run Python code",
                score=0.88,
                final_score=0.86,
                confidence="medium",
                skill_name="python",
                tool_name="run",
                file_path="python/scripts/run.py",
                routing_keywords=["python", "run", "execute"],
                input_schema='{"type": "object", "properties": {"code": {"type": "string"}}}',
                category="python",
            )
        ]

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=mock_results)
        search._store = mock_store

        results = await search.search("run python")

        assert len(results) == 1
        result = results[0]

        # All required fields should be present
        assert "id" in result
        assert "description" in result
        assert "score" in result
        assert "confidence" in result
        assert "final_score" in result
        assert "skill_name" in result
        assert "tool_name" in result
        assert "command" in result
        assert "file_path" in result
        assert "routing_keywords" in result
        assert "input_schema" in result
        assert "payload" in result
        assert "metadata" in result["payload"]
        assert result["tool_name"] == "python.run"
        assert result["routing_keywords"] == ["python", "run", "execute"]
        assert result["payload"]["metadata"]["tool_name"] == "python.run"
        assert result["payload"]["metadata"]["routing_keywords"] == ["python", "run", "execute"]
        assert result["payload"]["metadata"]["input_schema"]["type"] == "object"
        # Score breakdown from Rust is passed through for explain/transparency
        assert "vector_score" in result
        assert "keyword_score" in result
        assert result["vector_score"] == 0.81
        assert result["keyword_score"] == 0.74

    @pytest.mark.asyncio
    async def test_empty_results_on_error(self):
        """Test that empty list is returned on error."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(return_value=[])
        search._store = mock_store

        results = await search.search("nonexistent_tool_xyz")

        assert results == []

    @pytest.mark.asyncio
    async def test_invalid_payload_is_skipped(self):
        """Invalid tool-search payload should be ignored by parser."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(
            return_value=[
                {"name": "git.commit", "score": 0.9},  # missing schema/tool_name
            ]
        )
        search._store = mock_store
        results = await search.search("git commit")
        assert results == []

    @pytest.mark.asyncio
    async def test_uuid_like_tool_name_is_skipped(self):
        """UUID-like tool names must be filtered out from router results."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["search_tools"])
        mock_store.search_tools = AsyncMock(
            return_value=[
                {
                    "schema": "omni.vector.tool_search.v1",
                    "name": "6f9619ff-8b86-d011-b42d-00cf4fc964ff",
                    "description": "bad record",
                    "score": 0.95,
                    "final_score": 0.92,
                    "confidence": "high",
                    "skill_name": "unknown",
                    "tool_name": "6f9619ff-8b86-d011-b42d-00cf4fc964ff",
                    "file_path": "",
                    "routing_keywords": [],
                    "input_schema": "{}",
                    "intents": [],
                    "category": "unknown",
                },
                {
                    **make_tool_search_payload(
                        name="advanced_tools.smart_find",
                        tool_name="advanced_tools.smart_find",
                        description="Find files",
                        score=0.91,
                        final_score=0.89,
                        skill_name="advanced_tools",
                        file_path="assets/skills/advanced_tools/scripts/search.py",
                        routing_keywords=["find", "files"],
                        input_schema="{}",
                        category="search",
                    )
                },
            ]
        )
        search._store = mock_store
        results = await search.search("find python files")
        assert len(results) == 1
        assert results[0]["id"] == "advanced_tools.smart_find"


class TestQueryDecomposition:
    """Test intent/parameter decomposition for dual-signal search.

    Ensures keyword search receives intent-focused text (parameter tokens stripped)
    while embedding search keeps the full query for semantic understanding.
    """

    def test_extract_keyword_text_strips_github_url(self):
        """'research github url' → keyword text should be 'research'."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        assert _extract_keyword_text("research github url").strip() == "research"

    def test_extract_keyword_text_strips_plain_url_and_stops(self):
        """'help me fetch url' → keyword text strips 'url' and stop words, keeps 'fetch'."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        result = _extract_keyword_text("help me fetch url")
        assert "url" not in result.lower()
        assert "help" not in result.lower()
        assert "fetch" in result.lower()

    def test_extract_keyword_text_preserves_intent_words(self):
        """'git commit with message' → stop words removed, intent words kept."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        result = _extract_keyword_text("git commit with message")
        assert "git" in result
        assert "commit" in result
        assert "message" in result

    def test_extract_keyword_text_fallback_when_all_stripped(self):
        """If stripping leaves nothing, return original query."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        # "url" alone → strip leaves empty → fallback to original
        assert _extract_keyword_text("url") == "url"

    def test_extract_keyword_text_strips_link_and_stops(self):
        """'open link to project' → strips 'link' and stop words, keeps 'open', 'project'."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        result = _extract_keyword_text("open link to project")
        assert "link" not in result.lower()
        assert "to" not in result.split()
        assert "open" in result.lower()
        assert "project" in result.lower()

    def test_detect_param_types_url(self):
        """Detect URL param type from normalized query."""
        from omni.core.router.hybrid_search import _detect_param_types

        assert "url" in _detect_param_types("research github url")
        assert "url" in _detect_param_types("crawl url")
        assert "url" not in _detect_param_types("git commit")

    def test_detect_param_types_path(self):
        """Detect path param type from query with file path."""
        from omni.core.router.hybrid_search import _detect_param_types

        assert "path" in _detect_param_types("find files in /src/main")

    def test_query_has_concrete_url_uses_original_query(self):
        """_query_has_concrete_url must use original query; normalized query replaces URL with 'github url'."""
        from omni.core.router.hybrid_search import _query_has_concrete_url

        assert _query_has_concrete_url("help me research https://github.com/foo/bar") is True
        assert _query_has_concrete_url("help me research github url") is False
        assert _query_has_concrete_url("") is False

    def test_match_param_type_url_in_schema(self):
        """Schema with 'url' or 'repo_url' param matches URL type."""
        from omni.core.router.hybrid_search import _match_param_type_to_schema

        schema_with_url = {"properties": {"url": {"type": "string"}}}
        schema_with_repo_url = {"properties": {"repo_url": {"type": "string"}}}
        schema_without = {"properties": {"message": {"type": "string"}}}

        assert _match_param_type_to_schema("url", schema_with_url) is True
        assert _match_param_type_to_schema("url", schema_with_repo_url) is True
        assert _match_param_type_to_schema("url", schema_without) is False

    def test_param_schema_boost_applied(self):
        """Tools with matching parameter types in schema get a score boost."""
        from omni.core.router.hybrid_search import _apply_param_schema_boost

        results = [
            {
                "id": "a",
                "score": 1.0,
                "final_score": 1.0,
                "input_schema": '{"properties": {"url": {"type": "string"}}}',
            },
            {
                "id": "b",
                "score": 0.9,
                "final_score": 0.9,
                "input_schema": '{"properties": {"name": {"type": "string"}}}',
            },
        ]
        boosted = _apply_param_schema_boost(results, ["url"])
        score_a = next(r["score"] for r in boosted if r["id"] == "a")
        score_b = next(r["score"] for r in boosted if r["id"] == "b")
        assert score_a > 1.0  # boosted
        assert score_b == 0.9  # not boosted

    def test_is_researcher_like_tool(self):
        """Researcher-like tools have research/analyze AND repo/repository in routing_keywords."""
        from omni.core.router.hybrid_search import _is_researcher_like_tool

        assert (
            _is_researcher_like_tool({"routing_keywords": ["research", "analyze", "repo"]}) is True
        )
        assert _is_researcher_like_tool({"routing_keywords": ["research", "repository"]}) is True
        assert _is_researcher_like_tool({"routing_keywords": ["analyze_repo", "git"]}) is True
        assert _is_researcher_like_tool({"routing_keywords": ["research", "url"]}) is False
        assert _is_researcher_like_tool({"routing_keywords": ["crawl", "url"]}) is False

    def test_apply_research_url_boost_ranks_researcher_first(self):
        """Research+URL boost puts researcher-like tools above crawl-like when both have similar base scores."""
        from omni.core.router.hybrid_search import _apply_research_url_boost

        results = [
            {
                "id": "crawl4ai.crawl_url",
                "score": 1.0,
                "final_score": 1.0,
                "routing_keywords": ["crawl", "url", "fetch"],
            },
            {
                "id": "researcher.git_repo_analyer",
                "score": 0.95,
                "final_score": 0.95,
                "routing_keywords": ["research", "analyze", "repo", "repository"],
            },
        ]
        boosted = _apply_research_url_boost(results, "help me research github url", ["url"])
        top = boosted[0]
        assert "researcher" in top["id"]
        assert top["score"] > 1.0


class TestDualSignalSearchIntegration:
    """Test that search() passes intent-focused text to keyword engine."""

    @pytest.mark.asyncio
    async def test_search_sends_intent_text_to_keyword_engine(self):
        """When query contains URL tokens, keyword search receives stripped text."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["agentic_search", "get_search_profile"])
        mock_store.agentic_search = AsyncMock(return_value=[])
        mock_store.get_search_profile = MagicMock(
            return_value={
                "semantic_weight": 1.0,
                "keyword_weight": 1.5,
                "rrf_k": 10,
            }
        )
        search._store = mock_store

        await search.search("research github url", skip_translation=True)

        # agentic_search should have been called with stripped keyword text
        call_kwargs = mock_store.agentic_search.call_args
        query_text_sent = call_kwargs.kwargs.get("query_text") or call_kwargs[1].get("query_text")
        assert "url" not in query_text_sent.lower()
        assert "research" in query_text_sent.lower()

    @pytest.mark.asyncio
    async def test_research_url_keyword_includes_analyze_repo(self):
        """Regression: research+concrete URL must expand keyword with 'analyze repo' to favor researcher."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["agentic_search", "get_search_profile"])
        mock_store.agentic_search = AsyncMock(return_value=[])
        mock_store.get_search_profile = MagicMock(
            return_value={
                "semantic_weight": 1.0,
                "keyword_weight": 1.5,
                "rrf_k": 10,
            }
        )
        search._store = mock_store

        await search.search(
            "help me to research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl",
            skip_translation=True,
        )

        call_kwargs = mock_store.agentic_search.call_args
        query_text_sent = call_kwargs.kwargs.get("query_text") or call_kwargs[1].get("query_text")
        assert "analyze" in query_text_sent.lower()
        assert "repo" in query_text_sent.lower()

    @pytest.mark.asyncio
    async def test_search_passes_full_query_for_non_url(self):
        """When query has no URL tokens, keyword text is the full query."""
        from omni.core.router.hybrid_search import HybridSearch

        search = HybridSearch()
        _stub_embed(search)
        mock_store = MagicMock(spec=["agentic_search", "get_search_profile"])
        mock_store.agentic_search = AsyncMock(return_value=[])
        mock_store.get_search_profile = MagicMock(
            return_value={
                "semantic_weight": 1.0,
                "keyword_weight": 1.5,
                "rrf_k": 10,
            }
        )
        search._store = mock_store

        await search.search("git commit with message", skip_translation=True)

        call_kwargs = mock_store.agentic_search.call_args
        query_text_sent = call_kwargs.kwargs.get("query_text") or call_kwargs[1].get("query_text")
        # "with" is a stop word, removed; intent words kept
        assert "git" in query_text_sent
        assert "commit" in query_text_sent
        assert "message" in query_text_sent


class TestRecalibrateConfidence:
    """Test _recalibrate_confidence with hybrid absolute + relative thresholds."""

    @pytest.fixture()
    def balanced_profile(self) -> dict:
        return {
            "high_threshold": 0.75,
            "medium_threshold": 0.50,
            "high_base": 0.90,
            "high_scale": 0.05,
            "high_cap": 0.99,
            "medium_base": 0.60,
            "medium_scale": 0.30,
            "medium_cap": 0.89,
            "low_floor": 0.10,
        }

    def test_score_above_high_threshold_and_relative(self, balanced_profile):
        """Score >= high_threshold and within HIGH_RATIO of top → high."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 1.5, "confidence": "low", "final_score": 0.0},
            {"score": 1.2, "confidence": "low", "final_score": 0.0},
        ]
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[0]["confidence"] == "high"
        assert recalibrated[1]["confidence"] == "high"

    def test_high_absolute_but_low_relative_downgrades(self, balanced_profile):
        """Score passes absolute high but is far below top → downgraded to medium."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 2.0, "confidence": "low", "final_score": 0.0},
            {
                "score": 0.8,
                "confidence": "low",
                "final_score": 0.0,
            },  # 0.8 >= 0.75 but 0.8 < 2.0 * 0.65 = 1.3
        ]
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[0]["confidence"] == "high"
        assert recalibrated[1]["confidence"] == "medium"  # downgraded by relative check

    def test_medium_tier_assignment(self, balanced_profile):
        """Score in medium absolute range and within medium relative range."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 1.0, "confidence": "low", "final_score": 0.0},
            {"score": 0.6, "confidence": "low", "final_score": 0.0},
        ]
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[0]["confidence"] == "high"
        # 0.6 >= 0.50 (medium abs) but 0.6 < 1.0 * 0.65 = 0.65 (not rel high)
        # 0.6 >= 1.0 * 0.40 = 0.40 (rel medium) → medium
        assert recalibrated[1]["confidence"] == "medium"

    def test_low_tier_both_checks(self, balanced_profile):
        """Score below both absolute and relative medium thresholds → low."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 1.5, "confidence": "low", "final_score": 0.0},
            {"score": 0.3, "confidence": "low", "final_score": 0.0},
        ]
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[1]["confidence"] == "low"

    def test_clear_winner_promotion(self, balanced_profile):
        """#1 far ahead of #2 gets promoted even if relative check fails."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 0.6, "confidence": "low", "final_score": 0.0},  # abs=medium, but only result
            {"score": 0.3, "confidence": "low", "final_score": 0.0},
        ]
        # 0.6 >= medium_threshold (0.5) and gap=0.3 >= CLEAR_WINNER_GAP (0.15)
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[0]["confidence"] == "high"

    def test_final_score_uses_tier_formula(self, balanced_profile):
        """Final_score is re-computed per tier using profile formula."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        results = [
            {"score": 0.9, "confidence": "low", "final_score": 0.0},
        ]
        recalibrated = _recalibrate_confidence(results, balanced_profile)
        assert recalibrated[0]["confidence"] == "high"
        # final = min(0.90 + 0.9 * 0.05, 0.99) = 0.945
        assert abs(recalibrated[0]["final_score"] - 0.945) < 0.001

    def test_empty_results_passthrough(self, balanced_profile):
        """Empty list returns empty list."""
        from omni.core.router.hybrid_search import _recalibrate_confidence

        assert _recalibrate_confidence([], balanced_profile) == []

    def test_slash_in_keyword_text_is_normalized(self):
        """Slashes between intent words are replaced with spaces for Tantivy."""
        from omni.core.router.hybrid_search import _extract_keyword_text

        assert "analyze" in _extract_keyword_text("analyze/research")
        assert "research" in _extract_keyword_text("analyze/research")
        assert "/" not in _extract_keyword_text("analyze/research")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
