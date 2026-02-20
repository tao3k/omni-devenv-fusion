"""Tests for LinkGraphEnhancer - secondary enhancement layer for link-graph results."""

from __future__ import annotations

from omni.rag.link_graph.models import LinkGraphNote
from omni.rag.link_graph_enhancer import (
    LinkGraphEnhancer,
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
        refs = _extract_entity_refs_py("See [[xiuxian-wendao|knowledge crate]]")
        assert len(refs) == 1
        assert refs[0].name == "xiuxian-wendao"

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
# LinkGraphEnhancer
# ---------------------------------------------------------------------------


def _make_note(
    title: str = "Test Note",
    content: str = "",
    path: str = "docs/test.md",
    tags: list[str] | None = None,
) -> LinkGraphNote:
    """Helper to create a LinkGraphNote for testing."""
    return LinkGraphNote(
        path=path,
        abs_path=f"/project/{path}",
        title=title,
        raw_content=content,
        tags=tags or [],
        filename_stem=path.rsplit("/", 1)[-1].replace(".md", ""),
    )


class TestLinkGraphEnhancer:
    """Tests for the LinkGraphEnhancer secondary analysis pipeline."""

    def test_enhance_note_basic(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)  # No graph, Python-only mode
        note = _make_note(content="# Hello\n\nSome content about [[Python]]")
        result = enhancer.enhance_note(note)

        assert result.note is note
        assert len(result.entity_refs) == 1
        assert result.entity_refs[0].name == "Python"

    def test_enhance_note_with_frontmatter(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)
        content = "---\ntitle: Guide\ntags:\n  - tutorial\n---\n# Guide\n\nContent with [[Rust]]"
        note = _make_note(content=content)
        result = enhancer.enhance_note(note)

        assert result.frontmatter.title == "Guide"
        assert result.frontmatter.tags == ["tutorial"]
        assert len(result.entity_refs) == 1

    def test_enhance_note_infers_relations(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)
        content = "---\ntags:\n  - search\n---\nReferences [[LanceDB]] and [[Tantivy]]"
        note = _make_note(title="Hybrid Search", content=content)
        result = enhancer.enhance_note(note)

        # Should have DOCUMENTED_IN for entities + RELATED_TO for tags
        doc_rels = [r for r in result.relations if r["relation_type"] == "DOCUMENTED_IN"]
        tag_rels = [r for r in result.relations if r["relation_type"] == "RELATED_TO"]
        assert len(doc_rels) == 2  # LanceDB, Tantivy
        assert len(tag_rels) == 1  # search

    def test_enhance_skill_note(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)
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
        enhancer = LinkGraphEnhancer(graph=None)
        notes = [
            _make_note(title="A", content="About [[X]]"),
            _make_note(title="B", content="About [[Y]] and [[Z]]"),
        ]
        results = enhancer.enhance_notes(notes)
        assert len(results) == 2
        assert len(results[0].entity_refs) == 1
        assert len(results[1].entity_refs) == 2

    def test_ref_stats(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)
        content = "Links: [[A#tool]], [[B#tool]], [[C#concept]]"
        note = _make_note(content=content)
        result = enhancer.enhance_note(note)

        assert result.ref_stats["total_refs"] == 3
        assert result.ref_stats["unique_entities"] == 3

    def test_no_content(self) -> None:
        enhancer = LinkGraphEnhancer(graph=None)
        note = _make_note(content="")
        result = enhancer.enhance_note(note)

        assert result.frontmatter.title is None
        assert len(result.entity_refs) == 0
        assert result.ref_stats["total_refs"] == 0
