"""
LinkGraph retrieval plan schema API for policy contract validation.

This module freezes the policy payload crossing common retrieval layers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.link_graph.retrieval_plan.v1.schema.json"
SCHEMA_VERSION = "omni.link_graph.retrieval_plan.v1"
RetrievalMode = Literal["graph_only", "hybrid", "vector_only"]
ConfidenceLevel = Literal["none", "low", "medium", "high"]


def get_schema_path():
    """Path to shared LinkGraph retrieval plan schema."""
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
    """Cached validator for LinkGraph retrieval plan schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph retrieval plan schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from LinkGraph retrieval plan schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph retrieval plan schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"LinkGraph retrieval plan schema missing $id: {path}")
    return schema_id


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if retrieval plan payload violates schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"link_graph retrieval plan schema violation at {loc}: {first.message}")


def build_plan_record(
    *,
    requested_mode: RetrievalMode,
    selected_mode: RetrievalMode,
    reason: str,
    backend_name: str,
    graph_hit_count: int,
    source_hint_count: int,
    graph_confidence_score: float,
    graph_confidence_level: ConfidenceLevel,
    budget_candidate_limit: int,
    budget_max_sources: int,
    budget_rows_per_source: int,
) -> dict[str, Any]:
    """Build and validate canonical LinkGraph retrieval plan payload."""
    payload = {
        "schema": SCHEMA_VERSION,
        "requested_mode": str(requested_mode),
        "selected_mode": str(selected_mode),
        "reason": str(reason),
        "backend_name": str(backend_name),
        "graph_hit_count": int(graph_hit_count),
        "source_hint_count": int(source_hint_count),
        "graph_confidence_score": float(graph_confidence_score),
        "graph_confidence_level": str(graph_confidence_level),
        "budget": {
            "candidate_limit": int(budget_candidate_limit),
            "max_sources": int(budget_max_sources),
            "rows_per_source": int(budget_rows_per_source),
        },
    }
    validate(payload)
    return payload


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "ConfidenceLevel",
    "RetrievalMode",
    "build_plan_record",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
]
