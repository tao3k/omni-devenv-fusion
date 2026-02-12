"""Schema Singularity Phase 2: contract consistency and E2E snapshot matrix.

- All vector/router payload parsers reject legacy 'keywords' field.
- Route test JSON (with stats) and db search JSON snapshots locked; CI fails on field drift.
- Assertions and payloads use test-kit factories (no hardcoded dicts).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from omni.test_kit.fixtures.vector import (
    ROUTE_TEST_SCHEMA_V1,
    make_db_search_hybrid_result_list,
    make_db_search_vector_result_list,
    make_hybrid_payload,
    make_route_test_payload,
    make_router_result_payload,
    make_tool_search_payload,
    make_vector_payload,
)
from omni.foundation.services.vector_schema import (
    parse_hybrid_payload,
    parse_tool_search_payload,
    parse_vector_payload,
)


def _snapshots_dir() -> Path:
    return Path(__file__).resolve().parent / "snapshots"


def _schemas_dir() -> Path:
    from omni.foundation.config.paths import get_config_paths

    return get_config_paths().project_root / "packages" / "shared" / "schemas"


def _load_schema(name: str) -> dict:
    path = _schemas_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_items_against_schema(items: list[dict], schema: dict) -> None:
    validator = Draft202012Validator(schema)
    for i, item in enumerate(items):
        errors = list(validator.iter_errors(item))
        assert not errors, f"item[{i}] violates schema: {[e.message for e in errors]}"


# ---- P0: Contract consistency - all parsers reject legacy "keywords" ----


def test_tool_search_parser_rejects_keywords():
    payload = make_tool_search_payload()
    payload.pop("routing_keywords", None)
    payload["keywords"] = ["git", "commit"]
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        parse_tool_search_payload(payload)


def test_vector_parser_rejects_keywords():
    data = make_vector_payload()
    data["keywords"] = ["legacy"]
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        parse_vector_payload(json.dumps(data))


def test_hybrid_parser_rejects_keywords():
    data = make_hybrid_payload()
    data["keywords"] = ["legacy"]
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        parse_hybrid_payload(json.dumps(data))


# ---- P0: E2E snapshot matrix - route JSON (with stats), built from test-kit ----


def test_route_test_payload_built_from_factory_has_contract_shape():
    """Route test payload built from test-kit has required keys and no legacy keywords."""
    stats = {
        "semantic_weight": 1,
        "keyword_weight": 1.5,
        "rrf_k": 10,
        "strategy": "weighted_rrf_field_boosting",
    }
    payload = make_route_test_payload(
        query="git commit",
        results=[make_router_result_payload()],
        stats=stats,
    )
    assert payload["schema"] == ROUTE_TEST_SCHEMA_V1
    assert payload["query"] == "git commit"
    assert "stats" in payload
    assert payload["stats"]["semantic_weight"] == 1
    assert "results" in payload
    for r in payload["results"]:
        assert "routing_keywords" in r
        assert "keywords" not in r
        if "payload" in r and "metadata" in r["payload"]:
            assert "keywords" not in r["payload"]["metadata"]


def test_route_test_snapshot_matches_factory_output():
    """Snapshot equals test-kit factory output so CI fails on drift."""
    stats = {
        "semantic_weight": 1,
        "keyword_weight": 1.5,
        "rrf_k": 10,
        "strategy": "weighted_rrf_field_boosting",
    }
    expected = make_route_test_payload(
        query="git commit",
        results=[make_router_result_payload()],
        stats=stats,
    )
    path = _snapshots_dir() / "route_test_with_stats_contract_v1.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot == expected, "Snapshot must match make_route_test_payload() output"


# ---- P0: E2E snapshot matrix - db search JSON, built from test-kit ----


def test_db_search_vector_list_built_from_factory_validates_against_schema():
    """Db search vector result list from test-kit conforms to omni.vector.search.v1."""
    schema = _load_schema("omni.vector.search.v1.schema.json")
    items = make_db_search_vector_result_list()
    _validate_items_against_schema(items, schema)
    for item in items:
        assert "keywords" not in item


def test_db_search_hybrid_list_built_from_factory_validates_against_schema():
    """Db search hybrid result list from test-kit conforms to omni.vector.hybrid.v1."""
    schema = _load_schema("omni.vector.hybrid.v1.schema.json")
    items = make_db_search_hybrid_result_list()
    _validate_items_against_schema(items, schema)
    for item in items:
        assert "keywords" not in item


def test_db_search_vector_snapshot_matches_factory_output():
    """Snapshot equals test-kit factory output (vector list)."""
    expected = make_db_search_vector_result_list()
    path = _snapshots_dir() / "db_search_vector_result_contract_v1.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot == expected, "Snapshot must match make_db_search_vector_result_list()"


def test_db_search_hybrid_snapshot_matches_factory_output():
    """Snapshot equals test-kit factory output (hybrid list)."""
    expected = make_db_search_hybrid_result_list()
    path = _snapshots_dir() / "db_search_hybrid_result_contract_v1.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot == expected, "Snapshot must match make_db_search_hybrid_result_list()"
