"""Tests for omni.foundation.api.mcp_schema (MCP tool result shape and validation)."""

from __future__ import annotations

import pytest

from omni.foundation.api.mcp_schema import (
    CONTENT_KEY,
    IS_ERROR_KEY,
    build_result,
    enforce_result_shape,
    extract_text_content,
    is_canonical,
    parse_result_payload,
    validate,
)


def test_enforce_result_shape_strips_extra_keys():
    """enforce_result_shape returns only content and isError (schema-only)."""
    payload = {
        CONTENT_KEY: [{"type": "text", "text": "hello"}],
        IS_ERROR_KEY: False,
        "result": {"nested": "data"},
        "method": "tools/call",
    }
    out = enforce_result_shape(payload)
    assert list(out.keys()) == [CONTENT_KEY, IS_ERROR_KEY]
    assert out[CONTENT_KEY] == [{"type": "text", "text": "hello"}]
    assert out[IS_ERROR_KEY] is False


def test_enforce_result_shape_passes_validation():
    """enforce_result_shape output validates against shared schema when present."""
    from omni.foundation.api.mcp_schema import get_schema_path

    if not get_schema_path().exists():
        pytest.skip("Shared schema not found")
    payload = {
        CONTENT_KEY: [{"type": "text", "text": "x"}],
        IS_ERROR_KEY: True,
        "extra": "ignored",
    }
    out = enforce_result_shape(payload)
    validate(out)


def test_is_canonical_accepts_only_content_and_iserror():
    """is_canonical is True for dicts with content + isError and valid content[0]."""
    assert is_canonical({"content": [{"type": "text", "text": "x"}], "isError": False}) is True
    assert is_canonical({"content": [], "isError": False}) is False
    assert (
        is_canonical({"content": [{"type": "text", "text": "x"}], "isError": False, "result": {}})
        is True
    )


def test_build_result_is_schema_only():
    """build_result produces only content and isError."""
    out = build_result("hello")
    assert set(out.keys()) == {CONTENT_KEY, IS_ERROR_KEY}
    assert out[CONTENT_KEY][0]["text"] == "hello"
    assert out[IS_ERROR_KEY] is False


def test_parse_result_payload_supports_raw_dict() -> None:
    """Raw dict payload should pass through unchanged."""
    payload = {"status": "success", "results": [{"source": "doc.md"}]}
    assert parse_result_payload(payload) == payload


def test_parse_result_payload_supports_json_string() -> None:
    """JSON string payload should decode into dict."""
    payload = '{"status":"success","results":[{"source":"doc.md"}]}'
    parsed = parse_result_payload(payload)
    assert parsed["status"] == "success"
    assert parsed["results"] == [{"source": "doc.md"}]


def test_parse_result_payload_supports_canonical_json_text() -> None:
    """Canonical MCP payload should unwrap inner JSON text."""
    payload = {
        "content": [{"type": "text", "text": '{"status":"success","results":[{"source":"x"}]}'}],
        "isError": False,
    }
    parsed = parse_result_payload(payload)
    assert parsed["status"] == "success"
    assert parsed["results"] == [{"source": "x"}]


def test_extract_text_content_supports_jsonrpc_result() -> None:
    """extract_text_content should unwrap JSON-RPC result and read canonical text."""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [{"type": "text", "text": "hello world"}],
            "isError": False,
        },
    }
    assert extract_text_content(payload) == "hello world"


def test_extract_text_content_joins_multiple_content_items() -> None:
    """extract_text_content should preserve all text items in order."""
    payload = {
        "content": [
            {"type": "text", "text": "line one"},
            {"type": "text", "text": "line two"},
        ],
        "isError": False,
    }
    assert extract_text_content(payload) == "line one\nline two"


def test_extract_text_content_falls_back_to_error_message() -> None:
    """extract_text_content should extract JSON-RPC error messages."""
    payload = {
        "jsonrpc": "2.0",
        "id": "2",
        "error": {"code": -32603, "message": "internal error"},
    }
    assert extract_text_content(payload) == "internal error"
