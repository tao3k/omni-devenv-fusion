"""Tests for omni.foundation.api.link_graph_search_options_schema."""

from __future__ import annotations

import pytest

import omni.foundation.api.link_graph_search_options_schema as search_schema
from omni.foundation.api.link_graph_search_options_schema import (
    build_options_record,
    get_schema_id,
    validate,
)


def test_build_options_record_roundtrip() -> None:
    payload = build_options_record(
        match_strategy="exact",
        sort_terms=[{"field": "path", "order": "asc"}],
        case_sensitive=True,
        link_to=["architecture"],
        linked_by=["memory"],
        related=["router"],
        max_distance=3,
        related_ppr_alpha=0.9,
        related_ppr_max_iter=64,
        related_ppr_tol=1e-6,
        related_ppr_subgraph_mode="auto",
    )
    validate(payload)
    assert payload["match_strategy"] == "exact"
    assert payload["sort_terms"] == [{"field": "path", "order": "asc"}]
    assert payload["case_sensitive"] is True
    assert payload["filters"]["link_to"]["seeds"] == ["architecture"]
    assert payload["filters"]["linked_by"]["seeds"] == ["memory"]
    assert payload["filters"]["related"]["seeds"] == ["router"]
    assert payload["filters"]["related"]["max_distance"] == 3
    assert payload["filters"]["related"]["ppr"] == {
        "alpha": 0.9,
        "max_iter": 64,
        "tol": 1e-6,
        "subgraph_mode": "auto",
    }


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.link_graph.search_options.v2.schema.json")


def test_validate_rejects_invalid_strategy() -> None:
    with pytest.raises(ValueError, match="match_strategy"):
        validate(
            {
                "schema": "omni.link_graph.search_options.v2",
                "match_strategy": "bm25",
                "sort_terms": [{"field": "score", "order": "desc"}],
                "case_sensitive": False,
                "filters": {},
            }
        )


def test_validate_accepts_path_fuzzy_strategy() -> None:
    payload = build_options_record(
        match_strategy="path_fuzzy",
        sort_terms=[{"field": "score", "order": "desc"}],
        case_sensitive=False,
    )
    validate(payload)
    assert payload["match_strategy"] == "path_fuzzy"


def test_validate_rejects_invalid_max_distance() -> None:
    with pytest.raises(ValueError, match="max_distance"):
        validate(
            {
                "schema": "omni.link_graph.search_options.v2",
                "match_strategy": "fts",
                "sort_terms": [{"field": "score", "order": "desc"}],
                "case_sensitive": False,
                "filters": {"related": {"seeds": ["x"], "max_distance": 0}},
            }
        )


def test_validate_rejects_invalid_related_ppr_alpha() -> None:
    with pytest.raises(ValueError, match=r"filters\.related\.ppr\.alpha"):
        build_options_record(
            related=["x"],
            max_distance=2,
            related_ppr_alpha=1.5,
        )


def test_build_options_record_accepts_tree_filters() -> None:
    payload = build_options_record(
        scope="mixed",
        max_heading_level=3,
        max_tree_hops=2,
        collapse_to_doc=False,
        edge_types=["structural", "semantic"],
        per_doc_section_cap=4,
        min_section_words=32,
    )
    validate(payload)
    assert payload["filters"]["scope"] == "mixed"
    assert payload["filters"]["max_heading_level"] == 3
    assert payload["filters"]["max_tree_hops"] == 2
    assert payload["filters"]["collapse_to_doc"] is False
    assert payload["filters"]["edge_types"] == ["structural", "semantic"]
    assert payload["filters"]["per_doc_section_cap"] == 4
    assert payload["filters"]["min_section_words"] == 32


def test_validate_rejects_invalid_scope() -> None:
    with pytest.raises(ValueError, match=r"filters\.scope"):
        build_options_record(scope="all")  # type: ignore[arg-type]


def test_validate_rejects_invalid_edge_type() -> None:
    with pytest.raises(ValueError, match=r"filters\.edge_types"):
        build_options_record(edge_types=["semantic", "unknown"])  # type: ignore[list-item]


def test_get_validator_raises_when_schema_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    search_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(search_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="LinkGraph search options schema not found"):
        search_schema.get_validator()
    search_schema.get_validator.cache_clear()
