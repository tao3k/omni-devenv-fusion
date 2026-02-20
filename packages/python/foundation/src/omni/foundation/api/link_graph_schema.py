"""
Link-graph record schema API for packages/shared/schemas/omni.link_graph.record.v1.schema.json.

This module is the single validation entrypoint for link-graph payloads crossing
the Python/Rust boundary.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.link_graph.record.v1.schema.json"
SCHEMA_VERSION = "omni.link_graph.record.v1"
RecordKind = Literal["hit", "neighbor", "metadata"]
Direction = Literal["incoming", "outgoing", "both"]


def get_schema_path():
    """Path to the shared link-graph schema file."""
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
    """Cached JSON Schema validator for link-graph records."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"Link graph schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from shared link-graph schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"Link graph schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"Link graph schema missing $id: {path}")
    return schema_id


def validate(record: dict[str, Any]) -> None:
    """Raise ValueError if a record violates the shared schema."""
    errs = sorted(get_validator().iter_errors(record), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"link_graph schema violation at {loc}: {first.message}")


def build_record(
    *,
    kind: RecordKind,
    stem: str,
    title: str = "",
    path: str = "",
    score: float | None = None,
    best_section: str | None = None,
    match_reason: str | None = None,
    direction: Direction | None = None,
    distance: int | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build and validate a canonical link-graph record."""
    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "kind": kind,
        "stem": stem,
        "title": title,
        "path": path,
    }
    if score is not None or kind == "hit":
        payload["score"] = score
    if best_section is not None:
        payload["best_section"] = str(best_section)
    if match_reason is not None:
        payload["match_reason"] = str(match_reason)
    if direction is not None or kind == "neighbor":
        payload["direction"] = direction
    if distance is not None:
        payload["distance"] = distance
    if tags is not None or kind == "metadata":
        payload["tags"] = tags or []
    validate(payload)
    return payload


def validate_records(records: list[dict[str, Any]]) -> None:
    """Validate every record in a list."""
    for record in records:
        validate(record)


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "Direction",
    "RecordKind",
    "build_record",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
    "validate_records",
]
