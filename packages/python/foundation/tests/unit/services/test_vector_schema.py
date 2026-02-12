"""Unit tests for canonical vector payload schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from omni.test_kit.fixtures.vector import (
    make_hybrid_payload,
    make_tool_search_payload,
    make_vector_payload,
    parametrize_input_schema_variants,
    with_removed_key,
)
from pydantic import ValidationError

from omni.foundation.services.vector_schema import (
    HYBRID_SCHEMA_V1,
    TOOL_SEARCH_SCHEMA_V1,
    VECTOR_SCHEMA_V1,
    HybridPayload,
    SearchOptionsContract,
    ToolSearchPayload,
    VectorPayload,
    build_search_options_json,
    build_tool_router_result,
    parse_hybrid_payload,
    parse_tool_router_result,
    parse_tool_search_payload,
    parse_vector_payload,
    validate_vector_table_contract,
)


def test_parse_hybrid_payload_accepts_canonical_shape():
    raw = json.dumps(make_hybrid_payload())
    payload = parse_hybrid_payload(raw)
    assert isinstance(payload, HybridPayload)
    assert payload.schema_version == HYBRID_SCHEMA_V1
    rid, content, metadata, score = payload.to_search_result_fields()
    assert rid == "doc-1"
    assert content == "hello"
    assert score == 0.8
    assert metadata["debug_scores"]["vector_score"] == 0.3


def test_hybrid_payload_contract_snapshot_v1():
    raw = json.dumps(make_hybrid_payload())
    payload = parse_hybrid_payload(raw)
    rid, content, metadata, score = payload.to_search_result_fields()
    snapshot = {
        "id": rid,
        "content": content,
        "metadata": metadata,
        "source": payload.source,
        "score": score,
        "schema": payload.schema_version,
    }
    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "hybrid_payload_contract_v1.json"
    )
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot == expected


def test_parse_hybrid_payload_rejects_missing_schema():
    raw = json.dumps(with_removed_key(make_hybrid_payload(metadata={}), "schema"))
    with pytest.raises(ValidationError):
        parse_hybrid_payload(raw)


def test_parse_hybrid_payload_rejects_unknown_schema():
    raw = json.dumps(make_hybrid_payload(schema="omni.vector.hybrid.v2", metadata={}))
    with pytest.raises(ValueError, match="Unsupported hybrid schema"):
        parse_hybrid_payload(raw)


def test_parse_hybrid_payload_rejects_missing_required_fields():
    raw = json.dumps({"tool_name": "git.status", "rrf_score": 0.77})
    with pytest.raises(ValidationError):
        parse_hybrid_payload(raw)


def test_parse_vector_payload_accepts_canonical_shape():
    raw = json.dumps(make_vector_payload())
    payload = parse_vector_payload(raw)
    assert isinstance(payload, VectorPayload)
    assert payload.schema_version == VECTOR_SCHEMA_V1
    rid, content, metadata, distance = payload.to_search_result_fields()
    assert rid == "doc-1"
    assert content == "hello"
    assert distance == 0.2
    assert payload.score == 0.8333
    assert metadata["k"] == "v"


def test_vector_payload_contract_snapshot_v1():
    raw = json.dumps(make_vector_payload())
    payload = parse_vector_payload(raw)
    rid, content, metadata, distance = payload.to_search_result_fields()
    snapshot = {
        "id": rid,
        "content": content,
        "metadata": metadata,
        "distance": distance,
        "schema": payload.schema_version,
        "score": payload.score,
    }
    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "vector_payload_contract_v1.json"
    )
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot == expected


def test_parse_vector_payload_rejects_unknown_schema():
    raw = json.dumps(make_vector_payload(schema="omni.vector.search.v2", metadata={}))
    with pytest.raises(ValueError, match="Unsupported vector schema"):
        parse_vector_payload(raw)


def test_parse_vector_payload_rejects_missing_schema():
    raw = json.dumps(with_removed_key(make_vector_payload(metadata={}), "schema"))
    with pytest.raises(ValidationError):
        parse_vector_payload(raw)


def test_parse_vector_payload_rejects_legacy_keywords_field():
    data = make_vector_payload()
    data["keywords"] = ["legacy", "noise"]
    raw = json.dumps(data)
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        parse_vector_payload(raw)


def test_parse_hybrid_payload_rejects_legacy_keywords_field():
    data = make_hybrid_payload()
    data["keywords"] = ["legacy", "noise"]
    raw = json.dumps(data)
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        parse_hybrid_payload(raw)


def test_parse_tool_search_payload_accepts_canonical_shape():
    payload = parse_tool_search_payload(make_tool_search_payload(input_schema="{}"))
    assert isinstance(payload, ToolSearchPayload)
    assert payload.schema_version == TOOL_SEARCH_SCHEMA_V1
    router = payload.to_router_result()
    assert router["name"] == "git.commit"
    assert router["schema"] == TOOL_SEARCH_SCHEMA_V1
    assert isinstance(router["input_schema"], dict)
    assert router["routing_keywords"] == ["git", "commit"]
    assert router["command"] == "commit"
    assert router["payload"]["metadata"]["tool_name"] == "git.commit"
    assert router["payload"]["metadata"]["routing_keywords"] == ["git", "commit"]


@parametrize_input_schema_variants()
def test_parse_tool_search_payload_normalizes_input_schema_variants(
    input_schema_value: str | dict[str, Any],
):
    parsed = parse_tool_search_payload(make_tool_search_payload(input_schema=input_schema_value))
    assert parsed.input_schema["type"] == "object"


def test_parse_tool_search_payload_accepts_routing_keywords_field():
    payload = parse_tool_search_payload(
        make_tool_search_payload(
            name="advanced_tools.smart_find",
            tool_name="advanced_tools.smart_find",
            description="Find files by extension",
            score=0.83,
            vector_score=0.71,
            keyword_score=0.66,
            final_score=0.85,
            confidence="medium",
            skill_name="advanced_tools",
            file_path="assets/skills/advanced_tools/scripts/search.py",
            routing_keywords=["find", "files", "directory"],
            category="search",
        )
    )
    assert payload.routing_keywords == ["find", "files", "directory"]


def test_parse_tool_search_payload_rejects_legacy_keywords_field():
    with pytest.raises(ValueError, match="Legacy field 'keywords'"):
        payload = make_tool_search_payload(
            name="advanced_tools.smart_find",
            tool_name="advanced_tools.smart_find",
            skill_name="advanced_tools",
            file_path="assets/skills/advanced_tools/scripts/search.py",
            category="search",
        )
        payload.pop("routing_keywords", None)
        payload["keywords"] = ["find", "files", "directory"]
        parse_tool_search_payload(payload)


def test_parse_tool_search_payload_accepts_confidence_fields():
    payload = parse_tool_search_payload(
        make_tool_search_payload(input_schema="{}", final_score=0.95)
    )
    router = payload.to_router_result()
    assert router["final_score"] == 0.95
    assert router["confidence"] == "high"


def test_build_tool_router_result_uses_canonical_contract():
    payload = parse_tool_search_payload(
        make_tool_search_payload(
            name="advanced_tools.smart_find",
            tool_name="advanced_tools.smart_find",
            description="Find files by extension",
            score=0.88,
            final_score=0.89,
            skill_name="advanced_tools",
            file_path="assets/skills/advanced_tools/scripts/search.py",
            routing_keywords=["find", "files", "directory"],
            intents=["Locate files"],
            category="search",
        )
    )
    router = build_tool_router_result(payload, "advanced_tools.smart_find")
    parsed = parse_tool_router_result(router)
    assert parsed.tool_name == "advanced_tools.smart_find"
    assert parsed.command == "smart_find"
    assert parsed.routing_keywords == ["find", "files", "directory"]
    assert parsed.description == "Find files by extension"
    assert parsed.payload.description == "Find files by extension"
    assert parsed.payload.metadata.routing_keywords == ["find", "files", "directory"]
    assert "content" not in router
    assert "content" not in router["payload"]


def test_tool_router_result_contract_snapshot_v1():
    payload = parse_tool_search_payload(
        make_tool_search_payload(
            name="advanced_tools.smart_find",
            tool_name="advanced_tools.smart_find",
            description="Find files by extension",
            score=0.88,
            final_score=0.89,
            skill_name="advanced_tools",
            file_path="assets/skills/advanced_tools/scripts/search.py",
            routing_keywords=["find", "files", "directory"],
            intents=["Locate files"],
            category="search",
        )
    )
    router = build_tool_router_result(payload, "advanced_tools.smart_find")
    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "tool_router_result_contract_v1.json"
    )
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert router == expected


def test_tool_search_common_schema_file_exists():
    from omni.foundation.config.paths import get_config_paths

    root = get_config_paths().project_root / "packages" / "shared" / "schemas"
    tool_search_schema = root / "omni.vector.tool_search.v1.schema.json"
    vector_schema = root / "omni.vector.search.v1.schema.json"
    hybrid_schema = root / "omni.vector.hybrid.v1.schema.json"
    assert tool_search_schema.exists(), f"Missing common schema file: {tool_search_schema}"
    assert vector_schema.exists(), f"Missing common schema file: {vector_schema}"
    assert hybrid_schema.exists(), f"Missing common schema file: {hybrid_schema}"


def test_vector_payload_snapshot_validates_against_search_schema():
    """E2E: snapshot must conform to omni.vector.search.v1 JSON schema (CI drift guard)."""
    from jsonschema import Draft202012Validator

    from omni.foundation.config.paths import get_config_paths

    root = get_config_paths().project_root
    schema_path = root / "packages" / "shared" / "schemas" / "omni.vector.search.v1.schema.json"
    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "vector_payload_contract_v1.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert not errors, f"Snapshot violates schema: {[e.message for e in errors]}"


def test_hybrid_payload_snapshot_validates_against_hybrid_schema():
    """E2E: snapshot must conform to omni.vector.hybrid.v1 JSON schema (CI drift guard)."""
    from jsonschema import Draft202012Validator

    from omni.foundation.config.paths import get_config_paths

    root = get_config_paths().project_root
    schema_path = root / "packages" / "shared" / "schemas" / "omni.vector.hybrid.v1.schema.json"
    snapshot_path = (
        Path(__file__).resolve().parent / "snapshots" / "hybrid_payload_contract_v1.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))
    assert not errors, f"Snapshot violates schema: {[e.message for e in errors]}"


def test_tool_search_payload_snapshot_validates_against_tool_search_schema():
    """E2E: canonical tool_search payload validates against omni.vector.tool_search.v1 (CI drift guard)."""
    from jsonschema import Draft202012Validator

    from omni.foundation.config.paths import get_config_paths

    root = get_config_paths().project_root
    schema_path = (
        root / "packages" / "shared" / "schemas" / "omni.vector.tool_search.v1.schema.json"
    )
    canonical = make_tool_search_payload(
        name="advanced_tools.smart_find",
        tool_name="advanced_tools.smart_find",
        description="Find files by extension",
        routing_keywords=["find", "files", "directory"],
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(canonical))
    assert not errors, (
        f"Canonical tool_search payload violates schema: {[e.message for e in errors]}"
    )


def test_parse_tool_search_payload_accepts_superset_router_fields():
    payload = parse_tool_search_payload(
        make_tool_search_payload(
            command="commit",
            payload={"metadata": {"tool_name": "git.commit"}},
        )
    )
    assert payload.tool_name == "git.commit"
    assert payload.score == 0.91


def test_parse_tool_search_payload_rejects_unknown_schema():
    with pytest.raises(ValueError, match="Unsupported tool search schema"):
        parse_tool_search_payload(
            make_tool_search_payload(schema="omni.vector.tool_search.v2", input_schema="{}")
        )


def test_parse_tool_search_payload_rejects_missing_confidence_fields():
    with pytest.raises(ValidationError):
        parse_tool_search_payload(
            with_removed_key(
                with_removed_key(make_tool_search_payload(input_schema="{}"), "confidence"),
                "final_score",
            )
        )


def test_build_search_options_json_validates_and_serializes():
    payload = build_search_options_json(
        {
            "where_filter": '{"name":"tool.echo"}',
            "batch_size": 512,
            "fragment_readahead": 2,
            "batch_readahead": 8,
            "scan_limit": 64,
        }
    )
    assert payload is not None
    assert '"batch_size": 512' in payload


def test_build_search_options_json_rejects_invalid_range():
    with pytest.raises(ValidationError):
        build_search_options_json({"batch_size": 0})


def test_build_search_options_json_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        build_search_options_json({"foo": 1})


def test_search_options_schema_has_strict_additional_properties():
    schema = SearchOptionsContract.model_json_schema()
    assert schema.get("additionalProperties") is False


def test_validate_vector_table_contract_no_legacy():
    entries = [
        {"id": "a", "content": "x", "metadata": {"routing_keywords": ["git", "commit"]}},
        {"id": "b", "content": "y", "metadata": {"routing_keywords": []}},
    ]
    out = validate_vector_table_contract(entries)
    assert out["total"] == 2
    assert out["legacy_keywords_count"] == 0
    assert out["sample_ids"] == []


def test_validate_vector_table_contract_detects_legacy():
    entries = [
        {"id": "a", "content": "x", "metadata": {"routing_keywords": ["git"]}},
        {"id": "b", "keywords": ["legacy"], "content": "y"},
    ]
    out = validate_vector_table_contract(entries)
    assert out["total"] == 2
    assert out["legacy_keywords_count"] == 1
    assert out["sample_ids"] == ["b"]
