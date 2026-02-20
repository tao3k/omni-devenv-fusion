"""Tests for omni.foundation.api.link_graph_schema."""

from __future__ import annotations

import pytest

import omni.foundation.api.link_graph_schema as link_graph_schema
from omni.foundation.api.link_graph_schema import (
    build_record,
    get_schema_id,
    validate,
    validate_records,
)


def test_build_record_hit_roundtrip() -> None:
    payload = build_record(
        kind="hit",
        stem="knowledge-recall",
        title="Knowledge Recall",
        path="assets/skills/knowledge/scripts/recall.py",
        score=0.9,
        best_section="Architecture / Recall",
        match_reason="path_fuzzy+section_heading_contains",
    )
    validate(payload)
    assert payload["best_section"] == "Architecture / Recall"
    assert payload["match_reason"] == "path_fuzzy+section_heading_contains"


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.link_graph.record.v1.schema.json")


def test_build_record_neighbor_requires_direction() -> None:
    with pytest.raises(ValueError, match="direction"):
        validate({"schema": "omni.link_graph.record.v1", "kind": "neighbor", "stem": "x"})


def test_validate_records_rejects_invalid_item() -> None:
    good = build_record(kind="metadata", stem="a", tags=["tag1"])
    bad = {"schema": "omni.link_graph.record.v1", "kind": "hit", "stem": "", "score": 0.1}
    with pytest.raises(ValueError, match="stem"):
        validate_records([good, bad])


def test_get_validator_raises_when_schema_file_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    link_graph_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(link_graph_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="Link graph schema not found"):
        link_graph_schema.get_validator()
    link_graph_schema.get_validator.cache_clear()
