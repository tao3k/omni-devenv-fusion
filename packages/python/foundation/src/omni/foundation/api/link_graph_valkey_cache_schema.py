"""
LinkGraph Valkey cache snapshot schema API.

This module is the single validation entrypoint for the shared contract:
`packages/shared/schemas/omni.link_graph.valkey_cache_snapshot.v1.schema.json`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.link_graph.valkey_cache_snapshot.v1.schema.json"
SCHEMA_VERSION = "omni.link_graph.valkey_cache_snapshot.v1"


def get_schema_path():
    """Path to the shared LinkGraph Valkey cache schema file."""
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
    """Cached validator for LinkGraph Valkey cache snapshot schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph Valkey cache schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from LinkGraph Valkey cache schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph Valkey cache schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"LinkGraph Valkey cache schema missing $id: {path}")
    return schema_id


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload violates LinkGraph Valkey cache schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"link_graph valkey cache schema violation at {loc}: {first.message}")


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
]
