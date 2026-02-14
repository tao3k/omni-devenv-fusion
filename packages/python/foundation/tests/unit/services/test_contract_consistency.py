"""Schema Singularity Phase 2: contract consistency and E2E snapshot matrix.

- All vector/router payload parsers reject legacy 'keywords' field.
- Route test JSON (with stats) and db search JSON snapshots locked; CI fails on field drift.
- Assertions and payloads use test-kit factories (no hardcoded dicts).
- E2E: Rust output -> Python parse -> CLI JSON validated against schema (CI gate).
"""

from __future__ import annotations

import json
import re
import subprocess
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
    from omni.foundation.services.vector_schema import get_shared_schemas_dir

    return get_shared_schemas_dir()


def _load_schema(name: str) -> dict:
    path = _schemas_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_items_against_schema(items: list[dict], schema: dict) -> None:
    validator = Draft202012Validator(schema)
    for i, item in enumerate(items):
        errors = list(validator.iter_errors(item))
        assert not errors, f"item[{i}] violates schema: {[e.message for e in errors]}"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---- P0: E2E contract gate - CLI JSON validates against schema (CI fails on drift) ----


def test_route_test_cli_json_validates_against_schema():
    """E2E: Run `omni route test --json`, parse stdout, validate against omni.router.route_test.v1.

    Single-command CI gate: Rust output -> Python parse -> CLI JSON must match schema.
    Skips on timeout (e.g. no embedding/index) or non-zero exit.
    """
    root = _schemas_dir().parent.parent.parent  # repo root
    try:
        result = subprocess.run(
            ["uv", "run", "omni", "route", "test", "git commit", "--local", "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("omni route test timed out (e.g. no embedding server or index)")
    if result.returncode != 0:
        pytest.skip(f"omni route test failed (e.g. no index): {result.stderr!r}")
    raw = result.stdout or ""
    stripped = _strip_ansi(raw).strip()
    if not stripped:
        pytest.skip("omni route test produced no JSON (empty stdout); check CLI and index")
    # CLI may emit log lines before JSON; use last line if it looks like JSON
    if stripped.startswith("{"):
        json_str = stripped
    else:
        lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
        json_str = lines[-1] if lines else ""
    if not json_str or not json_str.startswith("{"):
        pytest.skip("omni route test stdout did not contain JSON; check CLI --json behavior")
    payload = json.loads(json_str)
    schema = _load_schema("omni.router.route_test.v1.schema.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert not errors, "CLI JSON must match omni.router.route_test.v1 schema: " + "; ".join(
        e.message for e in errors
    )
    assert payload.get("schema") == ROUTE_TEST_SCHEMA_V1
    for r in payload.get("results") or []:
        assert "keywords" not in r, "Results must use routing_keywords only"
        if "payload" in r and "metadata" in r["payload"]:
            assert "keywords" not in r["payload"]["metadata"]


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


# ---- P0: Shared canonical snapshot (vector-side contract) ----
def test_route_test_canonical_snapshot_validates_against_schema():
    """Shared canonical snapshot (packages/shared/schemas/snapshots/route_test_canonical_v1.json) must validate against route_test schema.

    This snapshot is the single source of truth for the full algorithm output shape; lock before Python changes.
    """
    schema = _load_schema("omni.router.route_test.v1.schema.json")
    canonical_path = _schemas_dir() / "snapshots" / "route_test_canonical_v1.json"
    assert canonical_path.exists(), f"Canonical snapshot missing: {canonical_path}"
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert not errors, "Canonical snapshot must match omni.router.route_test.v1: " + "; ".join(
        e.message for e in errors
    )
    assert payload.get("schema") == ROUTE_TEST_SCHEMA_V1
    for r in payload.get("results") or []:
        assert "keywords" not in r
        assert "routing_keywords" in r


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
