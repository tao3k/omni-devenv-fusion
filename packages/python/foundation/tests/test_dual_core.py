"""Tests for dual_core.py - Dual-Core Knowledge Fusion Engine.

Tests the four bridges that connect Core 1 (ZK) and Core 2 (LanceDB):
1. ZK Link Proximity Boost for recall results
2. LanceDB vector search function for ZK hybrid search
3. ZK entity graph enrichment for router skill relationships
4. Shared Entity Registry: skill docs → KnowledgeGraph (omni sync hook)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni.rag.dual_core import (
    build_vector_search_for_zk,
    enrich_skill_graph_from_zk,
    register_skill_entities,
    zk_link_proximity_boost,
    ZK_LINK_PROXIMITY_BOOST,
    ZK_TAG_PROXIMITY_BOOST,
    ZK_ENTITY_GRAPH_BOOST,
)

# ---------------------------------------------------------------------------
# Shared test constants — derived from module constants, not magic numbers
# ---------------------------------------------------------------------------

# Base scores for test fixtures (arbitrary but named)
_HIGH_SCORE = 0.8
_MID_SCORE = 0.6
_LOW_SCORE = 0.5
_VERY_LOW_SCORE = 0.3
_TOP_SCORE = 0.9
_ALT_SCORE = 0.7

# Expected boosted values
_HIGH_BOOSTED = _HIGH_SCORE + ZK_LINK_PROXIMITY_BOOST
_MID_BOOSTED = _MID_SCORE + ZK_LINK_PROXIMITY_BOOST

# Relationship graph weight thresholds
_STRONG_EDGE = 0.5
_MEDIUM_EDGE = 0.35


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_skill_script(skills_dir: Path, skill_name: str, script_name: str) -> Any:
    """Import a skill script via importlib using the skills_dir fixture."""
    script_path = skills_dir / skill_name / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(f"_skill_{script_name}", str(script_path))
    assert spec and spec.loader, f"Cannot load {script_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_mock_note(stem: str, tags: list[str] | None = None) -> MagicMock:
    """Create a mock ZK note."""
    note = MagicMock()
    note.filename_stem = stem
    note.tags = tags or []
    return note


def _make_result(source: str, score: float) -> dict[str, Any]:
    """Create a recall result dict."""
    return {"source": source, "score": score}


def _make_zk_client_mock(link_map: dict[str, list[str]]) -> AsyncMock:
    """Create a mock ZK client with a configurable link map.

    link_map: stem -> list of stems it links to (bidirectional).
    """

    async def _list_notes(**kwargs: Any) -> list[MagicMock]:
        linked_by = kwargs.get("linked_by", [])
        link_to = kwargs.get("link_to", [])

        for stem in linked_by:
            targets = link_map.get(stem, [])
            return [_make_mock_note(t) for t in targets]

        for stem in link_to:
            # Reverse lookup: who links to this stem?
            sources = [s for s, ts in link_map.items() if stem in ts]
            return [_make_mock_note(s) for s in sources]

        return []

    client = AsyncMock()
    client.list_notes = _list_notes
    return client


# ---------------------------------------------------------------------------
# Bridge 1: ZK Link Proximity Boost
# ---------------------------------------------------------------------------


class TestZkLinkProximityBoost:
    """Tests for zk_link_proximity_boost (Core 1 → Core 2 bridge)."""

    @pytest.mark.asyncio
    async def test_passthrough_empty_results(self) -> None:
        result = await zk_link_proximity_boost([], "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_passthrough_single_result(self) -> None:
        results = [_make_result("docs/a.md", _HIGH_SCORE)]
        result = await zk_link_proximity_boost(results, "test")
        assert len(result) == 1
        assert result[0]["score"] == _HIGH_SCORE

    @pytest.mark.asyncio
    async def test_graceful_when_zk_unavailable(self) -> None:
        results = [
            _make_result("docs/a.md", _HIGH_SCORE),
            _make_result("docs/b.md", _MID_SCORE),
        ]
        with patch("omni.rag.zk_integration.ZkClient", side_effect=ImportError("no zk")):
            result = await zk_link_proximity_boost(results, "test")
            assert len(result) == 2
            assert result[0]["score"] == _HIGH_SCORE

    @pytest.mark.asyncio
    async def test_boost_linked_documents(self) -> None:
        results = [
            _make_result("docs/router.md", _HIGH_SCORE),
            _make_result("docs/skill.md", _MID_SCORE),
            _make_result("docs/unrelated.md", _LOW_SCORE),
        ]

        mock_client = _make_zk_client_mock(
            {
                "router": ["skill"],
                "skill": ["router"],
            }
        )

        with patch("omni.rag.zk_integration.ZkClient", return_value=mock_client):
            boosted = await zk_link_proximity_boost(results, "test query")

        router = next(r for r in boosted if r["source"] == "docs/router.md")
        skill = next(r for r in boosted if r["source"] == "docs/skill.md")
        unrelated = next(r for r in boosted if r["source"] == "docs/unrelated.md")

        assert router["score"] == pytest.approx(_HIGH_BOOSTED, abs=0.01)
        assert skill["score"] == pytest.approx(_MID_BOOSTED, abs=0.01)
        assert unrelated["score"] == _LOW_SCORE

    @pytest.mark.asyncio
    async def test_results_resorted_after_boost(self) -> None:
        results = [
            _make_result("docs/a.md", _TOP_SCORE),
            _make_result("docs/b.md", _VERY_LOW_SCORE),
            _make_result("docs/c.md", _ALT_SCORE),
        ]

        mock_client = _make_zk_client_mock(
            {
                "a": ["b"],
                "b": ["a"],
            }
        )

        with patch("omni.rag.zk_integration.ZkClient", return_value=mock_client):
            boosted = await zk_link_proximity_boost(results, "test")

        scores = [r["score"] for r in boosted]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Bridge 2: LanceDB Vector Search for ZK
# ---------------------------------------------------------------------------


class TestBuildVectorSearchForZk:
    """Tests for build_vector_search_for_zk (Core 2 → Core 1 bridge)."""

    def test_returns_callable(self) -> None:
        fn = build_vector_search_for_zk()
        assert callable(fn)

    @pytest.mark.asyncio
    async def test_returns_list_on_failure(self) -> None:
        fn = build_vector_search_for_zk("nonexistent_collection")
        result = await fn("test query", limit=5)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_zk_compatible_dicts(self) -> None:
        mock_result = MagicMock()
        mock_result.id = "docs/test.md"
        mock_result.content = "Test content for vector search"
        mock_result.score = _HIGH_SCORE
        mock_result.metadata = {}

        mock_backend = AsyncMock()
        mock_backend.search.return_value = [mock_result]

        with patch("omni.rag.retrieval.lancedb.LanceRetrievalBackend", return_value=mock_backend):
            fn = build_vector_search_for_zk()
            results = await fn("test query", limit=5)

        assert len(results) == 1
        r = results[0]
        # Verify ZK-compatible keys
        for key in ("id", "filename_stem", "score", "source"):
            assert key in r, f"Missing key: {key}"
        assert r["source"] == "vector"
        assert r["filename_stem"] == "test"

    def test_custom_collection(self) -> None:
        fn = build_vector_search_for_zk("custom_collection")
        assert callable(fn)


# ---------------------------------------------------------------------------
# Bridge 3: ZK Entity Graph → Router Skill Relationships
# ---------------------------------------------------------------------------


def _setup_mock_knowledge_graph(
    search_map: dict[str, list[str]],
) -> tuple[MagicMock, MagicMock]:
    """Build mock omni_core_rs module with a configurable entity search.

    search_map: query_term -> list of entity names returned.
    Returns: (mock_module, mock_kg)
    """
    mock_kg = MagicMock()

    def _mock_search(query: str, limit: int) -> list[MagicMock]:
        names = search_map.get(query, [])
        entities = []
        for name in names:
            e = MagicMock()
            e.to_dict.return_value = json.dumps({"name": name})
            entities.append(e)
        return entities

    mock_kg.search_entities = _mock_search

    mock_module = MagicMock()
    mock_module.PyKnowledgeGraph = MagicMock(return_value=mock_kg)
    return mock_module, mock_kg


class TestEnrichSkillGraphFromZk:
    """Tests for enrich_skill_graph_from_zk (Core 1 → Router bridge)."""

    def test_passthrough_when_no_lance_dir(self, tmp_path: Path) -> None:
        original = {"git.commit": [("git.smart_commit", _MEDIUM_EDGE)]}
        result = enrich_skill_graph_from_zk(original, lance_dir=tmp_path / "nonexistent.lance")
        assert result == original

    def test_passthrough_empty_graph(self) -> None:
        result = enrich_skill_graph_from_zk({}, lance_dir=Path("/nonexistent"))
        assert result == {}

    def test_enrichment_with_shared_entities(self, tmp_path: Path) -> None:
        original = {
            "git.commit": [("git.smart_commit", _MEDIUM_EDGE)],
            "researcher.git_repo_analyer": [],
            "code.code_search": [],
        }

        # Both "git" parts and "researcher" parts resolve to entity "git"
        mock_module, _ = _setup_mock_knowledge_graph(
            {
                "git": ["git"],
                "researcher": ["git"],  # shares entity "git" with git.commit
            }
        )

        lance_dir = tmp_path / "knowledge.lance"
        (lance_dir / "kg_entities").mkdir(parents=True)

        with patch.dict(sys.modules, {"omni_core_rs": mock_module}):
            result = enrich_skill_graph_from_zk(original, lance_dir=lance_dir)

        git_neighbors = dict(result.get("git.commit", []))
        researcher_neighbors = dict(result.get("researcher.git_repo_analyer", []))

        has_new_edge = (
            "researcher.git_repo_analyer" in git_neighbors or "git.commit" in researcher_neighbors
        )
        assert has_new_edge, f"Expected shared-entity edge: {result}"

    def test_existing_higher_weight_preserved(self, tmp_path: Path) -> None:
        original = {
            "git.commit": [("git.smart_commit", _STRONG_EDGE)],
            "git.smart_commit": [("git.commit", _STRONG_EDGE)],
        }

        mock_module, _ = _setup_mock_knowledge_graph({"git": ["git"]})

        lance_dir = tmp_path / "knowledge.lance"
        (lance_dir / "kg_entities").mkdir(parents=True)

        with patch.dict(sys.modules, {"omni_core_rs": mock_module}):
            result = enrich_skill_graph_from_zk(original, lance_dir=lance_dir)

        git_neighbors = dict(result.get("git.commit", []))
        assert git_neighbors.get("git.smart_commit", 0) >= _STRONG_EDGE

    def test_graceful_when_rust_unavailable(self, tmp_path: Path) -> None:
        original = {"git.commit": [("git.status", _VERY_LOW_SCORE)]}
        lance_dir = tmp_path / "knowledge.lance"
        (lance_dir / "kg_entities").mkdir(parents=True)

        saved = sys.modules.get("omni_core_rs")
        sys.modules["omni_core_rs"] = None  # type: ignore[assignment]
        try:
            result = enrich_skill_graph_from_zk(original, lance_dir=lance_dir)
            assert result == original
        finally:
            if saved is not None:
                sys.modules["omni_core_rs"] = saved
            else:
                sys.modules.pop("omni_core_rs", None)


# ---------------------------------------------------------------------------
# Integration: skill command wiring
# ---------------------------------------------------------------------------


class TestSkillCommandWiring:
    """Tests that skill commands properly use DualCore bridges."""

    def test_zk_hybrid_uses_dual_core_vector_func(self, skills_dir: Path) -> None:
        mod = _import_skill_script(skills_dir, "knowledge", "zk_search.py")
        fn = mod._build_vector_search_func()
        assert callable(fn)

    def test_recall_imports_dual_core_boost(self, skills_dir: Path) -> None:
        mod = _import_skill_script(skills_dir, "knowledge", "recall.py")
        assert callable(mod._apply_dual_core_recall_boost)

    @pytest.mark.asyncio
    async def test_recall_dual_core_boost_graceful_fallback(self, skills_dir: Path) -> None:
        mod = _import_skill_script(skills_dir, "knowledge", "recall.py")

        results = [_make_result("a.md", _TOP_SCORE)]
        result = await mod._apply_dual_core_recall_boost(results, "test")
        assert result == results


# ---------------------------------------------------------------------------
# Integration: Router skill_relationships wiring
# ---------------------------------------------------------------------------


class TestRouterSkillRelationshipsWiring:
    """Tests that the router properly calls ZK enrichment."""

    def test_enrich_function_exists(self) -> None:
        from omni.core.router.skill_relationships import _enrich_with_zk_graph

        assert callable(_enrich_with_zk_graph)

    def test_enrich_graceful_fallback(self) -> None:
        from omni.core.router.skill_relationships import _enrich_with_zk_graph

        original = {"tool.a": [("tool.b", _VERY_LOW_SCORE)]}
        result = _enrich_with_zk_graph(original)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Bridge 4: Shared Entity Registry (omni sync hook)
# ---------------------------------------------------------------------------


def _make_skill_doc(
    doc_id: str,
    doc_type: str,
    skill_name: str,
    *,
    tool_name: str = "",
    content: str = "",
    routing_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Build a skill doc dict matching SkillIndexer output format."""
    return {
        "id": doc_id,
        "content": content or f"Description for {doc_id}",
        "metadata": {
            "type": doc_type,
            "skill_name": skill_name,
            "tool_name": tool_name,
            "routing_keywords": routing_keywords or [],
        },
    }


class TestRegisterSkillEntities:
    """Tests for register_skill_entities (Bridge 4: Core 2 → Core 1)."""

    def test_skipped_when_rust_unavailable(self, tmp_path: Path) -> None:
        saved = sys.modules.get("omni_core_rs")
        sys.modules["omni_core_rs"] = None  # type: ignore[assignment]
        try:
            result = register_skill_entities([], lance_dir=tmp_path / "knowledge.lance")
            assert result["status"] == "skipped"
        finally:
            if saved is not None:
                sys.modules["omni_core_rs"] = saved
            else:
                sys.modules.pop("omni_core_rs", None)

    def test_creates_lance_tables(self, tmp_path: Path) -> None:
        docs = [
            _make_skill_doc("git", "skill", "git"),
            _make_skill_doc(
                "git.commit",
                "command",
                "git",
                tool_name="git.commit",
                routing_keywords=["commit", "vcs"],
            ),
        ]
        lance_dir = tmp_path / "knowledge.lance"
        result = register_skill_entities(docs, lance_dir=lance_dir)

        if result["status"] == "skipped":
            pytest.skip("omni_core_rs not available")

        assert result["status"] == "success"
        assert result["entities_added"] > 0
        assert result["relations_added"] > 0
        assert (lance_dir / "kg_entities").exists()

    def test_entities_and_relations_counts(self, tmp_path: Path) -> None:
        docs = [
            _make_skill_doc("knowledge", "skill", "knowledge"),
            _make_skill_doc(
                "knowledge.recall",
                "command",
                "knowledge",
                tool_name="knowledge.recall",
                routing_keywords=["search", "recall"],
            ),
            _make_skill_doc(
                "knowledge.docs",
                "command",
                "knowledge",
                tool_name="knowledge.docs",
                routing_keywords=["search", "docs"],
            ),
        ]
        lance_dir = tmp_path / "knowledge.lance"
        result = register_skill_entities(docs, lance_dir=lance_dir)

        if result["status"] == "skipped":
            pytest.skip("omni_core_rs not available")

        # 1 skill + 2 tools + 3 unique keywords = 6 entities
        assert result["entities_added"] >= 6
        # CONTAINS: knowledge->recall, knowledge->docs = 2
        # RELATED_TO: recall->{search,recall}, docs->{search,docs} = 4
        assert result["relations_added"] >= 6

    def test_idempotent_registration(self, tmp_path: Path) -> None:
        docs = [_make_skill_doc("git", "skill", "git")]
        lance_dir = tmp_path / "knowledge.lance"

        r1 = register_skill_entities(docs, lance_dir=lance_dir)
        if r1["status"] == "skipped":
            pytest.skip("omni_core_rs not available")

        r2 = register_skill_entities(docs, lance_dir=lance_dir)
        # Second run should update, not duplicate
        assert r2["entities_added"] == 0

    def test_metadata_as_json_string(self, tmp_path: Path) -> None:
        """Metadata may arrive as a JSON string from LanceDB entries."""
        doc = {
            "id": "git",
            "content": "Git operations",
            "metadata": json.dumps(
                {
                    "type": "skill",
                    "skill_name": "git",
                }
            ),
        }
        lance_dir = tmp_path / "knowledge.lance"
        result = register_skill_entities([doc], lance_dir=lance_dir)

        if result["status"] == "skipped":
            pytest.skip("omni_core_rs not available")

        assert result["entities_added"] >= 1


# ---------------------------------------------------------------------------
# Dynamic Fusion Weights (intent → weight selection)
# ---------------------------------------------------------------------------


class TestFusionWeights:
    """Tests for compute_fusion_weights() — dynamic ZK vs LanceDB weighting."""

    def test_empty_query_returns_balanced(self):
        from omni.rag.dual_core import FusionWeights, compute_fusion_weights

        w = compute_fusion_weights("")
        assert isinstance(w, FusionWeights)
        assert w.zk_proximity_scale == 1.0
        assert w.kg_rerank_scale == 1.0
        assert w.vector_weight == 1.0
        assert w.keyword_weight == 1.0

    def test_knowledge_query_boosts_zk(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("search for knowledge about rust patterns")
        # Knowledge target → ZK boost
        assert w.zk_proximity_scale > 1.0
        assert w.kg_rerank_scale > 1.0
        assert w.intent_target == "knowledge"

    def test_code_query_boosts_vector(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("find the function in the codebase")
        # Code target → vector emphasis
        assert w.vector_weight >= 1.0
        assert w.zk_proximity_scale <= 1.0
        assert w.intent_target == "code"

    def test_git_commit_favors_tool_routing(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("commit my changes to git")
        assert w.keyword_weight >= 1.0
        assert w.intent_action == "commit"
        assert w.intent_target == "git"

    def test_research_query_emphasizes_graph(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("research about LanceDB architecture")
        assert w.kg_rerank_scale >= 1.0
        assert w.intent_action == "research"

    def test_intent_keywords_propagated(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("search python async patterns in code")
        assert len(w.intent_keywords) > 0
        assert "python" in w.intent_keywords
        assert "async" in w.intent_keywords
