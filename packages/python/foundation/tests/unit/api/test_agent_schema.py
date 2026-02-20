"""Tests for omni.foundation.api.agent_schema (server info shape and validation)."""

from __future__ import annotations

import pytest

from omni.foundation.api.agent_schema import (
    MESSAGE_KEY,
    NAME_KEY,
    PROTOCOL_VERSION_KEY,
    VERSION_KEY,
    build_server_info,
    validate,
)


def test_build_server_info_defaults():
    """build_server_info returns canonical shape with defaults."""
    out = build_server_info()
    assert out[NAME_KEY] == "omni-agent"
    assert out[VERSION_KEY] == "2.0.0"
    assert out[PROTOCOL_VERSION_KEY] == "2024-11-05"
    assert MESSAGE_KEY not in out


def test_build_server_info_with_message():
    """build_server_info includes message when provided."""
    out = build_server_info(message="Use POST for JSON-RPC.")
    assert out[MESSAGE_KEY] == "Use POST for JSON-RPC."


def test_build_server_info_validates_when_schema_exists():
    """build_server_info output validates against shared schema when present."""
    from omni.foundation.api.agent_schema import get_schema_path

    if not get_schema_path().exists():
        pytest.skip("Shared schema not found")
    out = build_server_info()
    validate(out)


def test_validate_rejects_extra_keys():
    """validate raises when payload has additionalProperties (schema has additionalProperties: false)."""
    from omni.foundation.api.agent_schema import get_schema_path

    if not get_schema_path().exists():
        pytest.skip("Shared schema not found")
    payload = {
        NAME_KEY: "omni-agent",
        VERSION_KEY: "2.0.0",
        PROTOCOL_VERSION_KEY: "2024-11-05",
        "extra": "not allowed",
    }
    with pytest.raises(ValueError, match="schema violation"):
        validate(payload)
