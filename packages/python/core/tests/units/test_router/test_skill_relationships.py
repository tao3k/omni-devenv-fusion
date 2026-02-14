"""Tests for skill relationship graph and associative rerank."""

import json
import tempfile
from pathlib import Path

import pytest

from omni.core.router.skill_relationships import (
    apply_relationship_rerank,
    build_graph_from_docs,
    build_graph_from_entries,
    build_relationship_graph,
    get_relationship_graph_path,
    load_relationship_graph,
    save_relationship_graph,
)


class TestBuildRelationshipGraph:
    """Relationship graph from routing_keywords overlap (Jaccard)."""

    def test_empty_docs_returns_empty_graph(self):
        assert build_relationship_graph([]) == {}

    def test_single_doc_returns_empty_edges(self):
        docs = [{"id": "git.commit", "metadata": {"routing_keywords": ["git", "commit"]}}]
        g = build_relationship_graph(docs)
        assert g == {"git.commit": []}

    def test_two_tools_with_overlap(self):
        docs = [
            {
                "id": "researcher.run",
                "metadata": {"routing_keywords": ["research", "analyze", "github"]},
            },
            {
                "id": "crawl4ai.crawl_url",
                "metadata": {"routing_keywords": ["crawl", "url", "research"]},
            },
        ]
        g = build_relationship_graph(docs)
        assert "researcher.run" in g
        assert "crawl4ai.crawl_url" in g
        # shared "research" -> Jaccard > 0
        assert len(g["researcher.run"]) >= 1
        assert any(rid == "crawl4ai.crawl_url" for rid, _ in g["researcher.run"])

    def test_build_graph_from_docs_filters_commands_only(self):
        docs = [
            {"id": "researcher", "metadata": {"type": "skill", "routing_keywords": []}},
            {
                "id": "researcher.run",
                "metadata": {"type": "command", "routing_keywords": ["research"]},
            },
        ]
        g = build_graph_from_docs(docs)
        assert "researcher.run" in g
        assert "researcher" not in g

    def test_same_skill_adds_edge(self):
        docs = [
            {
                "id": "git.commit",
                "metadata": {
                    "type": "command",
                    "skill_name": "git",
                    "routing_keywords": ["commit"],
                },
            },
            {
                "id": "git.status",
                "metadata": {
                    "type": "command",
                    "skill_name": "git",
                    "routing_keywords": ["status"],
                },
            },
        ]
        g = build_relationship_graph(docs)
        assert "git.commit" in g
        assert any(rid == "git.status" for rid, _ in g["git.commit"])
        assert any(rid == "git.commit" for rid, _ in g["git.status"])

    def test_shared_references_add_edge(self):
        docs = [
            {
                "id": "researcher.run",
                "metadata": {
                    "type": "command",
                    "skill_tools_refers": ["run_research_graph"],
                    "routing_keywords": [],
                },
            },
            {
                "id": "researcher.other",
                "metadata": {
                    "type": "command",
                    "skill_tools_refers": ["run_research_graph"],
                    "routing_keywords": [],
                },
            },
        ]
        g = build_relationship_graph(docs)
        assert "researcher.run" in g
        assert any(rid == "researcher.other" for rid, _ in g["researcher.run"])

    def test_build_graph_from_entries_filters_commands(self):
        entries = [
            {"id": "skill_id", "type": "skill"},
            {
                "id": "git.commit",
                "type": "command",
                "skill_name": "git",
                "routing_keywords": ["commit"],
            },
        ]
        g = build_graph_from_entries(entries)
        assert "git.commit" in g
        assert "skill_id" not in g


class TestSaveLoadGraph:
    def test_save_and_load_roundtrip(self):
        graph = {"a": [("b", 0.5), ("c", 0.3)], "b": [("a", 0.5)]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skill_relationships.json"
            save_relationship_graph(graph, path)
            assert path.is_file()
            loaded = load_relationship_graph(path)
            assert loaded == graph


class TestGetRelationshipGraphPath:
    def test_none_or_memory_returns_none(self):
        assert get_relationship_graph_path(None) is None
        assert get_relationship_graph_path(":memory:") is None

    def test_lance_path_uses_parent(self):
        p = get_relationship_graph_path("/cache/omni-vector/router.lance")
        assert p is not None
        assert p.name == "skill_relationships.json"
        assert "omni-vector" in str(p)

    def test_dir_path_uses_same_dir(self):
        p = get_relationship_graph_path("/cache/omni-vector")
        assert p is not None
        assert p == Path("/cache/omni-vector/skill_relationships.json")


class TestApplyRelationshipRerank:
    def test_empty_graph_unchanged(self):
        results = [{"id": "git.commit", "score": 1.0, "final_score": 1.0}]
        out = apply_relationship_rerank(results, None)
        assert out == results

    def test_related_result_gets_boost(self):
        results = [
            {"id": "researcher.run", "score": 0.9, "final_score": 0.9},
            {"id": "crawl4ai.crawl_url", "score": 0.7, "final_score": 0.7},
        ]
        graph = {"researcher.run": [("crawl4ai.crawl_url", 0.4)]}
        out = apply_relationship_rerank(results, graph, top_n=3, boost=0.06)
        assert len(out) == 2
        # crawl4ai should get boost and possibly reorder
        scores = {r["id"]: r["score"] for r in out}
        assert "crawl4ai.crawl_url" in scores
        assert scores["crawl4ai.crawl_url"] >= 0.7
