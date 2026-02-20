"""Tests for dual_core.py - Dual-Core Knowledge Fusion Engine.

Tests the four bridges that connect Core 1 (LinkGraph) and Core 2 (LanceDB):
1. LinkGraph proximity boost for recall results
2. Entity graph enrichment for router skill relationships
3. Shared Entity Registry: skill docs -> KnowledgeGraph (omni sync hook)
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from omni.rag.dual_core import (
    LINK_GRAPH_LINK_PROXIMITY_BOOST,
    LINK_GRAPH_TAG_PROXIMITY_BOOST,
    enrich_skill_graph_from_link_graph,
    link_graph_proximity_boost,
    register_skill_entities,
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

# Relationship graph weight thresholds
_STRONG_EDGE = 0.5
_MEDIUM_EDGE = 0.35


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_skill_script(skills_dir: Path, skill_name: str, script_name: str) -> Any:
    """Import a skill script via importlib using the skills_dir fixture."""
    script_path = skills_dir / skill_name / "scripts" / script_name
    mod_name = f"_skill_{script_name.replace('/', '_').replace('.py', '')}"
    spec = importlib.util.spec_from_file_location(mod_name, str(script_path))
    assert spec and spec.loader, f"Cannot load {script_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_mock_note(stem: str, tags: list[str] | None = None) -> MagicMock:
    """Create a mock graph note."""
    note = MagicMock()
    note.filename_stem = stem
    note.tags = tags or []
    return note


def _make_result(source: str, score: float) -> dict[str, Any]:
    """Create a recall result dict."""
    return {"source": source, "score": score}


# ---------------------------------------------------------------------------
# Bridge 1: LinkGraph Proximity Boost
# ---------------------------------------------------------------------------


class TestLinkGraphProximityBoost:
    """Tests for link_graph_proximity_boost (Core 1 → Core 2 bridge)."""

    @pytest.mark.asyncio
    async def test_passthrough_empty_results(self) -> None:
        result = await link_graph_proximity_boost([], "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_passthrough_single_result(self) -> None:
        results = [_make_result("docs/a.md", _HIGH_SCORE)]
        result = await link_graph_proximity_boost(results, "test")
        assert len(result) == 1
        assert result[0]["score"] == _HIGH_SCORE

    @pytest.mark.asyncio
    async def test_graceful_when_graph_backend_unavailable(self) -> None:
        results = [
            _make_result("docs/a.md", _HIGH_SCORE),
            _make_result("docs/b.md", _MID_SCORE),
        ]
        with patch(
            "omni.rag.link_graph.proximity.get_link_graph_backend", side_effect=RuntimeError
        ):
            result = await link_graph_proximity_boost(results, "test")
            assert len(result) == 2
            assert result[0]["score"] == _HIGH_SCORE

    @pytest.mark.asyncio
    async def test_boost_linked_documents(self) -> None:
        results = [
            _make_result("docs/router.md", _HIGH_SCORE),
            _make_result("docs/skill.md", _MID_SCORE),
            _make_result("docs/unrelated.md", _LOW_SCORE),
        ]

        class _MockBackend:
            backend_name = "dual_core_test"

            async def neighbors(self, stem: str, **kwargs):
                del kwargs
                links = {"router": ["skill"], "skill": ["router"]}
                return [types.SimpleNamespace(stem=s) for s in links.get(stem, [])]

            async def metadata(self, stem: str):
                tags = {"router": ["shared"], "skill": ["shared"]}
                return types.SimpleNamespace(stem=stem, tags=tags.get(stem, []))

        with patch(
            "omni.rag.link_graph.proximity.get_link_graph_backend",
            return_value=_MockBackend(),
        ):
            boosted = await link_graph_proximity_boost(results, "test query")

        router = next(r for r in boosted if r["source"] == "docs/router.md")
        skill = next(r for r in boosted if r["source"] == "docs/skill.md")
        unrelated = next(r for r in boosted if r["source"] == "docs/unrelated.md")

        expected_pair_boost = LINK_GRAPH_LINK_PROXIMITY_BOOST + LINK_GRAPH_TAG_PROXIMITY_BOOST
        assert router["score"] == pytest.approx(_HIGH_SCORE + expected_pair_boost, abs=0.01)
        assert skill["score"] == pytest.approx(_MID_SCORE + expected_pair_boost, abs=0.01)
        assert unrelated["score"] == _LOW_SCORE

    @pytest.mark.asyncio
    async def test_results_resorted_after_boost(self) -> None:
        results = [
            _make_result("docs/a.md", _TOP_SCORE),
            _make_result("docs/b.md", _VERY_LOW_SCORE),
            _make_result("docs/c.md", _ALT_SCORE),
        ]

        class _MockBackend:
            backend_name = "dual_core_test_sort"

            async def neighbors(self, stem: str, **kwargs):
                del kwargs
                links = {"a": ["b"], "b": ["a"]}
                return [types.SimpleNamespace(stem=s) for s in links.get(stem, [])]

            async def metadata(self, stem: str):
                return types.SimpleNamespace(stem=stem, tags=[])

        with patch(
            "omni.rag.link_graph.proximity.get_link_graph_backend",
            return_value=_MockBackend(),
        ):
            boosted = await link_graph_proximity_boost(results, "test")

        scores = [r["score"] for r in boosted]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_skips_uuid_sources_no_graph_lookup(self) -> None:
        """LanceDB chunk IDs (UUIDs) are not passed to graph lookup."""
        uuid_source = "e077e713-3e85-46c2-ad01-6fb4c10722fc"
        results = [
            _make_result("docs/real-note.md", _HIGH_SCORE),
            _make_result(uuid_source, _MID_SCORE),
        ]

        class _MockBackend:
            backend_name = "dual_core_test_uuid"

            async def neighbors(self, stem: str, **kwargs):
                del stem, kwargs
                return []

            async def metadata(self, stem: str):
                return types.SimpleNamespace(stem=stem, tags=[])

        with patch(
            "omni.rag.link_graph.proximity.get_link_graph_backend",
            return_value=_MockBackend(),
        ):
            boosted = await link_graph_proximity_boost(results, "test")
        assert len(boosted) == 2
        uuid_result = next(r for r in boosted if r["source"] == uuid_source)
        assert uuid_result["score"] == _MID_SCORE


# ---------------------------------------------------------------------------
# Bridge 2: Entity Graph -> Router Skill Relationships
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
    mock_module.load_kg_from_lance_cached = MagicMock(return_value=mock_kg)
    return mock_module, mock_kg


class TestEnrichSkillGraphFromLinkGraph:
    """Tests for enrich_skill_graph_from_link_graph (Core 1 -> Router bridge)."""

    def test_passthrough_when_no_lance_dir(self, tmp_path: Path) -> None:
        original = {"git.commit": [("git.smart_commit", _MEDIUM_EDGE)]}
        result = enrich_skill_graph_from_link_graph(
            original, lance_dir=tmp_path / "nonexistent.lance"
        )
        assert result == original

    def test_passthrough_empty_graph(self) -> None:
        result = enrich_skill_graph_from_link_graph({}, lance_dir=Path("/nonexistent"))
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
            result = enrich_skill_graph_from_link_graph(original, lance_dir=lance_dir)

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
            result = enrich_skill_graph_from_link_graph(original, lance_dir=lance_dir)

        git_neighbors = dict(result.get("git.commit", []))
        assert git_neighbors.get("git.smart_commit", 0) >= _STRONG_EDGE

    def test_graceful_when_rust_unavailable(self, tmp_path: Path) -> None:
        original = {"git.commit": [("git.status", _VERY_LOW_SCORE)]}
        lance_dir = tmp_path / "knowledge.lance"
        (lance_dir / "kg_entities").mkdir(parents=True)

        saved = sys.modules.get("omni_core_rs")
        sys.modules["omni_core_rs"] = None  # type: ignore[assignment]
        try:
            result = enrich_skill_graph_from_link_graph(original, lance_dir=lance_dir)
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

    def test_hybrid_search_exports_run_entry(self, skills_dir: Path) -> None:
        mod = _import_skill_script(skills_dir, "knowledge", "search/hybrid.py")
        assert callable(mod.run_hybrid_search)

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
    """Tests that the router properly calls LinkGraph enrichment."""

    def test_enrich_function_exists(self) -> None:
        from omni.core.router.skill_relationships import _enrich_with_link_graph

        assert callable(_enrich_with_link_graph)

    def test_enrich_graceful_fallback(self) -> None:
        from omni.core.router.skill_relationships import _enrich_with_link_graph

        original = {"tool.a": [("tool.b", _VERY_LOW_SCORE)]}
        result = _enrich_with_link_graph(original)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Bridge 3: Shared Entity Registry (omni sync hook)
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
    """Tests for register_skill_entities (Bridge 3: Core 2 → Core 1)."""

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
    """Tests for compute_fusion_weights() — dynamic graph vs LanceDB weighting."""

    def test_empty_query_returns_balanced(self):
        from omni.rag.dual_core import FusionWeights, compute_fusion_weights

        w = compute_fusion_weights("")
        assert isinstance(w, FusionWeights)
        assert w.link_graph_proximity_scale == 1.0
        assert w.kg_rerank_scale == 1.0
        assert w.vector_weight == 1.0
        assert w.keyword_weight == 1.0

    def test_knowledge_query_boosts_graph(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("search for knowledge about rust patterns")
        # Knowledge target -> graph boost.
        assert w.link_graph_proximity_scale > 1.0
        assert w.kg_rerank_scale > 1.0
        assert w.intent_target == "knowledge"

    def test_code_query_boosts_vector(self):
        from omni.rag.dual_core import compute_fusion_weights

        w = compute_fusion_weights("find the function in the codebase")
        # Code target → vector emphasis
        assert w.vector_weight >= 1.0
        assert w.link_graph_proximity_scale <= 1.0
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
