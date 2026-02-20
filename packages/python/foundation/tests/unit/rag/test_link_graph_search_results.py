"""Tests for common LinkGraph search-result adapters."""

from __future__ import annotations

import pytest

from omni.rag.link_graph.models import LinkGraphHit
from omni.rag.link_graph.search_results import (
    link_graph_hits_to_hybrid_results,
    link_graph_hits_to_search_results,
    merge_hybrid_results,
    neighbors_to_link_rows,
    normalize_link_graph_direction,
    vector_rows_to_hybrid_results,
)


def test_link_graph_hits_to_search_results_has_stable_shape() -> None:
    hits = [
        LinkGraphHit(
            stem="architecture",
            score=0.9,
            title="Architecture",
            path="docs/arch.md",
            best_section="Architecture / Graph",
            match_reason="path_fuzzy+section_heading_contains",
        ),
        LinkGraphHit(stem="router", score=0.5, title="Router", path="docs/router.md"),
    ]
    out = link_graph_hits_to_search_results(hits)
    assert len(out) == 2
    assert out[0]["id"] == "architecture"
    assert out[0]["source"] == "graph_search"
    assert out[0]["section"] == "Architecture / Graph"
    assert out[0]["reasoning"] == "path_fuzzy+section_heading_contains"
    assert out[1]["score"] == pytest.approx(0.5, abs=1e-6)


def test_vector_rows_to_hybrid_results_falls_back_to_distance_score() -> None:
    rows = [
        {"source": "docs/a.md", "distance": 0.2, "content": "A"},
        {"source": "docs/b.md", "score": 0.7, "title": "B"},
    ]
    out = vector_rows_to_hybrid_results(rows)
    assert len(out) == 2
    assert out[0]["note"]["id"] == "a"
    assert out[0]["score"] == pytest.approx(0.8, abs=1e-6)
    assert out[1]["score"] == pytest.approx(0.7, abs=1e-6)
    assert out[1]["source"] == "vector"


def test_merge_hybrid_results_marks_overlap_as_hybrid() -> None:
    graph_rows = link_graph_hits_to_hybrid_results(
        [LinkGraphHit(stem="a", score=0.6, title="Doc A", path="docs/a.md")]
    )
    vector_rows = vector_rows_to_hybrid_results(
        [{"source": "docs/a.md", "score": 0.9, "content": "A body"}]
    )
    merged = merge_hybrid_results(graph_rows, vector_rows)

    assert len(merged) == 1
    assert merged[0]["source"] == "hybrid"
    assert merged[0]["score"] == pytest.approx(0.9, abs=1e-6)
    assert "LinkGraph search hit" in merged[0]["reasoning"]
    assert "Vector recall hit" in merged[0]["reasoning"]


def test_normalize_link_graph_direction_supports_cli_aliases() -> None:
    assert normalize_link_graph_direction("to").value == "incoming"
    assert normalize_link_graph_direction("from").value == "outgoing"
    assert normalize_link_graph_direction("both").value == "both"


def test_neighbors_to_link_rows_expands_both_direction() -> None:
    class _Neighbor:
        def __init__(self, stem: str, direction: str):
            self.stem = stem
            self.title = stem.upper()
            self.path = f"docs/{stem}.md"
            self.direction = direction

    outgoing, incoming = neighbors_to_link_rows(
        [
            _Neighbor("a", "incoming"),
            _Neighbor("b", "outgoing"),
            _Neighbor("c", "both"),
        ]
    )

    assert [row["id"] for row in incoming] == ["a", "c"]
    assert [row["id"] for row in outgoing] == ["b", "c"]
    assert incoming[0]["type"] == "incoming"
    assert outgoing[0]["type"] == "outgoing"
