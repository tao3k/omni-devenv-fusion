"""Tests for ZkEnhancer - secondary enhancement layer for ZK results."""

from __future__ import annotations

import pytest

from omni.rag.zk_client import ZkNote
from omni.rag.zk_enhancer import (
    EntityRef,
    FrontmatterData,
    ZkEnhancer,
    _extract_entity_refs_py,
    _parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for YAML frontmatter extraction."""

    def test_basic_frontmatter(self) -> None:
        content = "---\ntitle: My Note\ndescription: A test note\ntags:\n  - python\n  - rust\n---\n# Content"
        fm = _parse_frontmatter(content)
        assert fm.title == "My Note"
        assert fm.description == "A test note"
        assert fm.tags == ["python", "rust"]

    def test_skill_frontmatter(self) -> None:
        content = "---\nname: git\ndescription: Git operations\nmetadata:\n  routing_keywords:\n    - commit\n    - branch\n  intents:\n    - version_control\n---\n# SKILL"
        fm = _parse_frontmatter(content)
        assert fm.name == "git"
        assert fm.routing_keywords == ["commit", "branch"]
        assert fm.intents == ["version_control"]

    def test_no_frontmatter(self) -> None:
        content = "# Just a heading\n\nSome content"
        fm = _parse_frontmatter(content)
        assert fm.title is None
        assert fm.tags == []

    def test_empty_content(self) -> None:
        fm = _parse_frontmatter("")
        assert fm.title is None

    def test_malformed_yaml(self) -> None:
        content = "---\n: bad yaml [[\n---\n"
        fm = _parse_frontmatter(content)
        # Should not raise, returns empty
        assert fm.title is None


# ---------------------------------------------------------------------------
# Entity reference extraction (Python fallback)
# ---------------------------------------------------------------------------


class TestEntityExtraction:
    """Tests for wikilink entity reference extraction."""

    def test_simple_wikilink(self) -> None:
        refs = _extract_entity_refs_py("See [[Python]] for details")
        assert len(refs) == 1
        assert refs[0].name == "Python"
        assert refs[0].entity_type is None

    def test_typed_wikilink(self) -> None:
        refs = _extract_entity_refs_py("Uses [[KnowledgeGraph#rust]] internally")
        assert len(refs) == 1
        assert refs[0].name == "KnowledgeGraph"
        assert refs[0].entity_type == "rust"

    def test_aliased_wikilink(self) -> None:
        refs = _extract_entity_refs_py("See [[omni-knowledge|knowledge crate]]")
        assert len(refs) == 1
        assert refs[0].name == "omni-knowledge"

    def test_multiple_refs(self) -> None:
        content = "Links to [[Python]], [[Rust#lang]], and [[LanceDB]]."
        refs = _extract_entity_refs_py(content)
        assert len(refs) == 3
        names = {r.name for r in refs}
        assert names == {"Python", "Rust", "LanceDB"}

    def test_deduplication(self) -> None:
        content = "Both [[Python]] and [[Python]] should be one."
        refs = _extract_entity_refs_py(content)
        assert len(refs) == 1

    def test_no_wikilinks(self) -> None:
        refs = _extract_entity_refs_py("No links here.")
        assert len(refs) == 0


# ---------------------------------------------------------------------------
# ZkEnhancer
# ---------------------------------------------------------------------------


def _make_note(
    title: str = "Test Note",
    content: str = "",
    path: str = "docs/test.md",
    tags: list[str] | None = None,
) -> ZkNote:
    """Helper to create a ZkNote for testing."""
    return ZkNote(
        path=path,
        abs_path=f"/project/{path}",
        title=title,
        raw_content=content,
        tags=tags or [],
        filename_stem=path.rsplit("/", 1)[-1].replace(".md", ""),
    )


class TestZkEnhancer:
    """Tests for the ZkEnhancer secondary analysis pipeline."""

    def test_enhance_note_basic(self) -> None:
        enhancer = ZkEnhancer(graph=None)  # No graph, Python-only mode
        note = _make_note(content="# Hello\n\nSome content about [[Python]]")
        result = enhancer.enhance_note(note)

        assert result.note is note
        assert len(result.entity_refs) == 1
        assert result.entity_refs[0].name == "Python"

    def test_enhance_note_with_frontmatter(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        content = "---\ntitle: Guide\ntags:\n  - tutorial\n---\n# Guide\n\nContent with [[Rust]]"
        note = _make_note(content=content)
        result = enhancer.enhance_note(note)

        assert result.frontmatter.title == "Guide"
        assert result.frontmatter.tags == ["tutorial"]
        assert len(result.entity_refs) == 1

    def test_enhance_note_infers_relations(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        content = "---\ntags:\n  - search\n---\nReferences [[LanceDB]] and [[Tantivy]]"
        note = _make_note(title="Hybrid Search", content=content)
        result = enhancer.enhance_note(note)

        # Should have DOCUMENTED_IN for entities + RELATED_TO for tags
        doc_rels = [r for r in result.relations if r["relation_type"] == "DOCUMENTED_IN"]
        tag_rels = [r for r in result.relations if r["relation_type"] == "RELATED_TO"]
        assert len(doc_rels) == 2  # LanceDB, Tantivy
        assert len(tag_rels) == 1  # search

    def test_enhance_skill_note(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        content = "---\nname: git\ndescription: Git ops\n---\n# SKILL"
        note = _make_note(
            title="Git Skill",
            content=content,
            path="assets/skills/git/SKILL.md",
        )
        result = enhancer.enhance_note(note)

        contains_rels = [r for r in result.relations if r["relation_type"] == "CONTAINS"]
        assert len(contains_rels) == 1
        assert contains_rels[0]["source"] == "git"

    def test_enhance_batch(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        notes = [
            _make_note(title="A", content="About [[X]]"),
            _make_note(title="B", content="About [[Y]] and [[Z]]"),
        ]
        results = enhancer.enhance_notes(notes)
        assert len(results) == 2
        assert len(results[0].entity_refs) == 1
        assert len(results[1].entity_refs) == 2

    def test_ref_stats(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        content = "Links: [[A#tool]], [[B#tool]], [[C#concept]]"
        note = _make_note(content=content)
        result = enhancer.enhance_note(note)

        assert result.ref_stats["total_refs"] == 3
        assert result.ref_stats["unique_entities"] == 3

    def test_no_content(self) -> None:
        enhancer = ZkEnhancer(graph=None)
        note = _make_note(content="")
        result = enhancer.enhance_note(note)

        assert result.frontmatter.title is None
        assert len(result.entity_refs) == 0
        assert result.ref_stats["total_refs"] == 0


# ---------------------------------------------------------------------------
# ZkReasoningSearcher + enhancer integration
# ---------------------------------------------------------------------------


class TestSearcherEnhancerIntegration:
    """Tests that ZkReasoningSearcher correctly wires with ZkEnhancer."""

    def test_searcher_has_enhancer(self) -> None:
        from omni.rag.zk_search import ZkReasoningSearcher

        searcher = ZkReasoningSearcher(notebook_dir="/tmp")
        assert searcher.enhancer is not None

    def test_searcher_custom_enhancer(self) -> None:
        from omni.rag.zk_search import ZkReasoningSearcher

        custom = ZkEnhancer(graph=None)
        searcher = ZkReasoningSearcher(notebook_dir="/tmp", enhancer=custom)
        assert searcher.enhancer is custom

    def test_enhance_results_no_crash_on_empty(self) -> None:
        from omni.rag.zk_search import ZkReasoningSearcher

        searcher = ZkReasoningSearcher(notebook_dir="/tmp")
        # Should not crash with empty list
        searcher._enhance_results([])


# ---------------------------------------------------------------------------
# ZkHybridSearcher graph boost
# ---------------------------------------------------------------------------


class TestHybridGraphBoost:
    """Tests for entity graph boost in ZkHybridSearcher."""

    def test_hybrid_searcher_has_enhancer(self) -> None:
        from omni.rag.zk_search import ZkHybridSearcher

        searcher = ZkHybridSearcher(notebook_dir="/tmp")
        assert searcher.enhancer is not None
        assert searcher.zk_searcher.enhancer is searcher.enhancer

    def test_hybrid_searcher_shared_enhancer(self) -> None:
        from omni.rag.zk_search import ZkHybridSearcher

        custom = ZkEnhancer(graph=None)
        searcher = ZkHybridSearcher(notebook_dir="/tmp", enhancer=custom)
        assert searcher.enhancer is custom
        assert searcher.zk_searcher.enhancer is custom

    def test_graph_boost_no_crash_without_graph(self) -> None:
        from omni.rag.zk_search import ZkHybridSearcher

        searcher = ZkHybridSearcher(notebook_dir="/tmp", enhancer=ZkEnhancer(graph=None))
        merged = {"test": {"note": None, "score": 0.5, "source": "zk", "reasoning": "test"}}
        result = searcher._apply_graph_boost(merged, "python search")
        assert result["test"]["score"] == 0.5  # No boost applied
