"""Tests for omni.foundation.api.link_graph_policy_schema."""

from __future__ import annotations

import pytest

import omni.foundation.api.link_graph_policy_schema as link_graph_policy_schema
from omni.foundation.api.link_graph_policy_schema import build_plan_record, get_schema_id, validate


def test_build_plan_record_roundtrip() -> None:
    payload = build_plan_record(
        requested_mode="hybrid",
        selected_mode="graph_only",
        reason="graph_sufficient",
        backend_name="wendao",
        graph_hit_count=4,
        source_hint_count=3,
        graph_confidence_score=0.78,
        graph_confidence_level="high",
        budget_candidate_limit=20,
        budget_max_sources=8,
        budget_rows_per_source=8,
    )
    validate(payload)
    assert payload["schema"] == "omni.link_graph.retrieval_plan.v1"
    assert payload["budget"]["candidate_limit"] == 20


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.link_graph.retrieval_plan.v1.schema.json")


def test_validate_rejects_invalid_confidence_level() -> None:
    payload = build_plan_record(
        requested_mode="hybrid",
        selected_mode="vector_only",
        reason="graph_insufficient",
        backend_name="wendao",
        graph_hit_count=0,
        source_hint_count=0,
        graph_confidence_score=0.0,
        graph_confidence_level="none",
        budget_candidate_limit=10,
        budget_max_sources=5,
        budget_rows_per_source=8,
    )
    payload["graph_confidence_level"] = "bad"
    with pytest.raises(ValueError, match="graph_confidence_level"):
        validate(payload)


def test_get_validator_raises_when_schema_file_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    link_graph_policy_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(link_graph_policy_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="retrieval plan schema not found"):
        link_graph_policy_schema.get_validator()
    link_graph_policy_schema.get_validator.cache_clear()
