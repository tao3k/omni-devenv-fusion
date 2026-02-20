"""
Checkpoint record schema API - single place for packages/shared/schemas/omni.checkpoint.record.v1.

Load, validate, and build checkpoint payloads that conform to the shared schema
before crossing the Python -> Rust checkpoint boundary.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.checkpoint.record.v1.schema.json"
CHECKPOINT_ID_KEY = "checkpoint_id"
THREAD_ID_KEY = "thread_id"
TIMESTAMP_KEY = "timestamp"
CONTENT_KEY = "content"
PARENT_ID_KEY = "parent_id"
EMBEDDING_KEY = "embedding"
METADATA_KEY = "metadata"


def get_schema_path():
    """Path to the shared checkpoint record schema file."""
    from omni.foundation.config.paths import get_config_paths

    primary = get_config_paths().project_root / "packages" / "shared" / "schemas" / SCHEMA_NAME
    if primary.exists():
        return primary
    try:
        from omni.foundation.runtime.gitops import get_project_root

        fallback = get_project_root() / "packages" / "shared" / "schemas" / SCHEMA_NAME
        if fallback.exists():
            return fallback
    except Exception:
        pass
    return primary


@lru_cache(maxsize=1)
def get_validator() -> Draft202012Validator:
    """Cached validator for the checkpoint record schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from the shared checkpoint schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"Checkpoint schema missing $id: {path}")
    return schema_id


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload violates the shared checkpoint schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"checkpoint schema violation at {loc}: {first.message}")


def validate_checkpoint_write(
    table_name: str,
    payload: dict[str, Any],
    *,
    expected_embedding_dim: int | None = None,
) -> None:
    """Validate full checkpoint write contract (table + payload + semantic checks)."""
    if not table_name or not table_name.strip():
        raise ValueError("checkpoint table_name must be a non-empty string")

    validate(payload)

    checkpoint_id = payload[CHECKPOINT_ID_KEY]
    parent_id = payload.get(PARENT_ID_KEY)
    if parent_id is not None and parent_id == checkpoint_id:
        raise ValueError("checkpoint parent_id cannot equal checkpoint_id")

    timestamp = float(payload[TIMESTAMP_KEY])
    if not math.isfinite(timestamp):
        raise ValueError("checkpoint timestamp must be finite")

    content = payload[CONTENT_KEY]
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"checkpoint content must be valid JSON text: {exc}") from exc

    metadata = payload.get(METADATA_KEY)
    if metadata is not None:
        parsed = json.loads(metadata)
        if not isinstance(parsed, dict):
            raise ValueError("checkpoint metadata must be a JSON object string")

    embedding = payload.get(EMBEDDING_KEY)
    if embedding is not None:
        if expected_embedding_dim is not None and len(embedding) != expected_embedding_dim:
            raise ValueError(
                f"checkpoint embedding length mismatch: expected {expected_embedding_dim}, got {len(embedding)}"
            )
        if any(not math.isfinite(float(v)) for v in embedding):
            raise ValueError("checkpoint embedding contains non-finite values")


def build_payload(
    checkpoint_id: str,
    thread_id: str,
    timestamp: float,
    content: str,
    parent_id: str | None = None,
    embedding: list[float] | None = None,
    metadata: str | None = None,
) -> dict[str, Any]:
    """Build a canonical checkpoint payload and validate it."""
    payload = {
        CHECKPOINT_ID_KEY: checkpoint_id,
        THREAD_ID_KEY: thread_id,
        TIMESTAMP_KEY: timestamp,
        CONTENT_KEY: content,
        PARENT_ID_KEY: parent_id,
        EMBEDDING_KEY: embedding,
        METADATA_KEY: metadata,
    }
    validate(payload)
    return payload


__all__ = [
    "CHECKPOINT_ID_KEY",
    "CONTENT_KEY",
    "EMBEDDING_KEY",
    "METADATA_KEY",
    "PARENT_ID_KEY",
    "SCHEMA_NAME",
    "THREAD_ID_KEY",
    "TIMESTAMP_KEY",
    "build_payload",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
    "validate_checkpoint_write",
]
