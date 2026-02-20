"""Tests for omni.foundation.api.checkpoint_schema."""

from __future__ import annotations

import math

import pytest

import omni.foundation.api.checkpoint_schema as checkpoint_schema
from omni.foundation.api.checkpoint_schema import (
    build_payload,
    get_schema_id,
    validate,
    validate_checkpoint_write,
)


def test_build_payload_and_validate_roundtrip() -> None:
    """A canonical checkpoint payload should validate against shared schema."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1234.56,
        content='{"state":{"ok":true}}',
        parent_id=None,
        embedding=None,
        metadata='{"reason":"test"}',
    )
    validate(payload)


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.checkpoint.record.v1.schema.json")


def test_validate_checkpoint_write_rejects_empty_table_name() -> None:
    """table_name must be non-empty."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1.0,
        content='{"state":{}}',
    )
    with pytest.raises(ValueError, match="table_name"):
        validate_checkpoint_write("", payload)


def test_validate_checkpoint_write_rejects_non_object_metadata() -> None:
    """metadata must decode to JSON object when provided."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1.0,
        content='{"state":{}}',
        metadata="[]",
    )
    with pytest.raises(ValueError, match="metadata must be a JSON object"):
        validate_checkpoint_write("checkpoint_test", payload)


def test_validate_checkpoint_write_rejects_invalid_content_json() -> None:
    """content must be valid JSON text."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1.0,
        content='{"broken"',
    )
    with pytest.raises(ValueError, match="content must be valid JSON text"):
        validate_checkpoint_write("checkpoint_test", payload)


def test_validate_checkpoint_write_rejects_self_parent_id() -> None:
    """parent_id must not equal checkpoint_id."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1.0,
        content='{"state":{}}',
        parent_id="cp-1",
    )
    with pytest.raises(ValueError, match="parent_id cannot equal checkpoint_id"):
        validate_checkpoint_write("checkpoint_test", payload)


def test_validate_checkpoint_write_rejects_non_finite_timestamp() -> None:
    """timestamp must be finite."""
    payload = {
        "checkpoint_id": "cp-1",
        "thread_id": "thread-1",
        "timestamp": math.inf,
        "content": '{"state":{}}',
        "parent_id": None,
        "embedding": None,
        "metadata": None,
    }
    with pytest.raises(ValueError, match="timestamp must be finite"):
        validate_checkpoint_write("checkpoint_test", payload)


def test_validate_checkpoint_write_rejects_embedding_dim_mismatch() -> None:
    """embedding length must match expected dimension when provided."""
    payload = build_payload(
        checkpoint_id="cp-1",
        thread_id="thread-1",
        timestamp=1.0,
        content='{"state":{}}',
        embedding=[0.1, 0.2],
    )
    with pytest.raises(ValueError, match="embedding length mismatch"):
        validate_checkpoint_write("checkpoint_test", payload, expected_embedding_dim=3)


def test_validate_checkpoint_write_rejects_non_finite_embedding_value() -> None:
    """embedding must not contain NaN/inf."""
    payload = {
        "checkpoint_id": "cp-1",
        "thread_id": "thread-1",
        "timestamp": 1.0,
        "content": '{"state":{}}',
        "parent_id": None,
        "embedding": [0.1, math.nan],
        "metadata": None,
    }
    with pytest.raises(ValueError, match="embedding contains non-finite values"):
        validate_checkpoint_write("checkpoint_test", payload)


def test_get_validator_raises_when_schema_file_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing shared schema file should fail fast with clear error."""
    checkpoint_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(checkpoint_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="Checkpoint schema not found"):
        checkpoint_schema.get_validator()
    payload = {
        "checkpoint_id": "cp-1",
        "thread_id": "thread-1",
        "timestamp": 1.0,
        "content": '{"state":{}}',
        "parent_id": None,
        "embedding": None,
        "metadata": None,
    }
    with pytest.raises(FileNotFoundError, match="Checkpoint schema not found"):
        validate_checkpoint_write("checkpoint_test", payload)
    checkpoint_schema.get_validator.cache_clear()
