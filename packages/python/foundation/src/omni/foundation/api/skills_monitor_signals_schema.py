"""
Skills monitor signals schema API for strict runtime contract validation.

This module validates machine-readable monitor signals against the shared schema.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.skills_monitor.signals.v1.schema.json"
SCHEMA_VERSION = "omni.skills_monitor.signals.v1"


def get_schema_path():
    """Path to shared skills monitor signals schema."""
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
    """Cached validator for skills monitor signals schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"skills monitor signals schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from skills monitor signals schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"skills monitor signals schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"skills monitor signals schema missing $id: {path}")
    return schema_id


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload violates skills monitor signals schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"skills monitor signals schema violation at {loc}: {first.message}")


def build_payload(
    *,
    retrieval_signals: dict[str, Any] | None,
    link_graph_signals: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build and validate canonical skills monitor signals payload."""
    payload = {
        "schema": SCHEMA_VERSION,
        "retrieval_signals": retrieval_signals,
        "link_graph_signals": link_graph_signals,
    }
    validate(payload)
    return payload


def validate_signals(
    *,
    retrieval_signals: dict[str, Any] | None,
    link_graph_signals: dict[str, Any] | None,
) -> None:
    """Validate retrieval/link_graph monitor signals pair against shared schema."""
    build_payload(
        retrieval_signals=retrieval_signals,
        link_graph_signals=link_graph_signals,
    )


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "build_payload",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
    "validate_signals",
]
