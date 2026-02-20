"""
LinkGraph search options schema API for backend search contract validation.

This module freezes search options payloads crossing common Python/Rust layers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

SCHEMA_NAME = "omni.link_graph.search_options.v2.schema.json"
SCHEMA_VERSION = "omni.link_graph.search_options.v2"
MatchStrategy = Literal["fts", "path_fuzzy", "exact", "re"]
SortField = Literal["score", "path", "title", "stem", "created", "modified", "random", "word_count"]
SortOrder = Literal["asc", "desc"]
Scope = Literal["doc_only", "section_only", "mixed"]
EdgeType = Literal["structural", "semantic", "provisional", "verified"]
PprSubgraphMode = Literal["auto", "disabled", "force"]

_VALID_SORT_FIELDS = {
    "score",
    "path",
    "title",
    "stem",
    "created",
    "modified",
    "random",
    "word_count",
}
_VALID_SORT_ORDERS = {"asc", "desc"}
_VALID_SCOPES = {"doc_only", "section_only", "mixed"}
_VALID_EDGE_TYPES = {"structural", "semantic", "provisional", "verified"}
_VALID_PPR_SUBGRAPH_MODES = {"auto", "disabled", "force"}


def _clean_string_list(items: list[Any] | tuple[Any, ...] | None) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _coerce_sort_terms(sort_terms: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    if not sort_terms:
        return [{"field": "score", "order": "desc"}]
    out: list[dict[str, str]] = []
    for term in sort_terms:
        field = str((term or {}).get("field", "score")).strip().lower()
        order = str((term or {}).get("order", "desc")).strip().lower()
        if field not in _VALID_SORT_FIELDS:
            raise ValueError(
                f"link_graph search options schema violation at sort_terms.field: unknown sort field '{field}'"
            )
        if order not in _VALID_SORT_ORDERS:
            raise ValueError(
                f"link_graph search options schema violation at sort_terms.order: unknown sort order '{order}'"
            )
        out.append({"field": field, "order": order})
    return out


def _build_link_filter_record(
    seeds: list[Any] | tuple[Any, ...] | None,
    *,
    negate: bool = False,
    recursive: bool = False,
    max_distance: int | None = None,
) -> dict[str, Any] | None:
    cleaned_seeds = _clean_string_list(cast("list[Any] | tuple[Any, ...] | None", seeds))
    if not cleaned_seeds:
        return None
    payload: dict[str, Any] = {
        "seeds": cleaned_seeds,
    }
    if negate:
        payload["negate"] = True
    if recursive:
        payload["recursive"] = True
    if max_distance is not None:
        payload["max_distance"] = int(max_distance)
    return payload


def _coerce_scope(scope: str | None) -> str | None:
    if scope is None:
        return None
    normalized = str(scope).strip().lower()
    if not normalized:
        return None
    if normalized not in _VALID_SCOPES:
        raise ValueError(
            f"link_graph search options schema violation at filters.scope: unknown scope '{normalized}'"
        )
    return normalized


def _coerce_edge_types(edge_types: list[str] | tuple[str, ...] | None) -> list[str]:
    cleaned = _clean_string_list(cast("list[Any] | tuple[Any, ...] | None", edge_types))
    if not cleaned:
        return []
    out: list[str] = []
    for edge_type in cleaned:
        normalized = edge_type.strip().lower()
        if normalized not in _VALID_EDGE_TYPES:
            raise ValueError(
                "link_graph search options schema violation at filters.edge_types: "
                f"unknown edge type '{normalized}'"
            )
        if normalized not in out:
            out.append(normalized)
    return out


def _coerce_related_ppr_payload(
    *,
    related_ppr: dict[str, Any] | None = None,
    alpha: float | None = None,
    max_iter: int | None = None,
    tol: float | None = None,
    subgraph_mode: str | None = None,
) -> dict[str, Any] | None:
    payload = related_ppr if isinstance(related_ppr, dict) else {}
    out: dict[str, Any] = {}

    alpha_value = alpha if alpha is not None else payload.get("alpha")
    if alpha_value is not None:
        out["alpha"] = float(alpha_value)

    max_iter_value = max_iter if max_iter is not None else payload.get("max_iter")
    if max_iter_value is not None:
        out["max_iter"] = int(max_iter_value)

    tol_value = tol if tol is not None else payload.get("tol")
    if tol_value is not None:
        out["tol"] = float(tol_value)

    subgraph_mode_value = (
        subgraph_mode if subgraph_mode is not None else payload.get("subgraph_mode")
    )
    if subgraph_mode_value is not None:
        normalized = str(subgraph_mode_value).strip().lower()
        if normalized not in _VALID_PPR_SUBGRAPH_MODES:
            raise ValueError(
                "link_graph search options schema violation at filters.related.ppr.subgraph_mode: "
                f"unknown mode '{normalized}'"
            )
        out["subgraph_mode"] = normalized

    return out or None


def get_schema_path():
    """Path to shared LinkGraph search options schema."""
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
    """Cached validator for LinkGraph search options schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph search options schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_schema_id() -> str:
    """Return JSON schema `$id` from LinkGraph search options schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"LinkGraph search options schema not found: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema_id = str(schema.get("$id", "")).strip()
    if not schema_id:
        raise ValueError(f"LinkGraph search options schema missing $id: {path}")
    return schema_id


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if search options payload violates schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"link_graph search options schema violation at {loc}: {first.message}")


def build_options_record(
    *,
    match_strategy: MatchStrategy = "fts",
    case_sensitive: bool = False,
    sort_terms: list[dict[str, Any]] | None = None,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    tags_all: list[str] | None = None,
    tags_any: list[str] | None = None,
    tags_not: list[str] | None = None,
    link_to: list[str] | None = None,
    link_to_negate: bool = False,
    link_to_recursive: bool = False,
    link_to_max_distance: int | None = None,
    linked_by: list[str] | None = None,
    linked_by_negate: bool = False,
    linked_by_recursive: bool = False,
    linked_by_max_distance: int | None = None,
    related: list[str] | None = None,
    max_distance: int | None = None,
    related_ppr: dict[str, Any] | None = None,
    related_ppr_alpha: float | None = None,
    related_ppr_max_iter: int | None = None,
    related_ppr_tol: float | None = None,
    related_ppr_subgraph_mode: PprSubgraphMode | None = None,
    mentions_of: list[str] | None = None,
    mentioned_by_notes: list[str] | None = None,
    orphan: bool = False,
    tagless: bool = False,
    missing_backlink: bool = False,
    scope: Scope | None = None,
    max_heading_level: int | None = None,
    max_tree_hops: int | None = None,
    collapse_to_doc: bool | None = None,
    edge_types: list[EdgeType] | None = None,
    per_doc_section_cap: int | None = None,
    min_section_words: int | None = None,
    created_after: int | None = None,
    created_before: int | None = None,
    modified_after: int | None = None,
    modified_before: int | None = None,
) -> dict[str, Any]:
    """Build and validate canonical LinkGraph search options payload."""
    normalized_match = str(match_strategy).strip().lower()
    payload = {
        "schema": SCHEMA_VERSION,
        "match_strategy": normalized_match,
        "case_sensitive": bool(case_sensitive),
        "sort_terms": _coerce_sort_terms(sort_terms),
        "filters": {},
    }

    filters: dict[str, Any] = {}
    include_row = _clean_string_list(include_paths)
    if include_row:
        filters["include_paths"] = include_row
    exclude_row = _clean_string_list(exclude_paths)
    if exclude_row:
        filters["exclude_paths"] = exclude_row

    tags_row: dict[str, Any] = {}
    tags_all_row = _clean_string_list(tags_all)
    if tags_all_row:
        tags_row["all"] = tags_all_row
    tags_any_row = _clean_string_list(tags_any)
    if tags_any_row:
        tags_row["any"] = tags_any_row
    tags_not_row = _clean_string_list(tags_not)
    if tags_not_row:
        tags_row["not"] = tags_not_row
    if tags_row:
        filters["tags"] = tags_row

    link_to_row = _build_link_filter_record(
        link_to,
        negate=link_to_negate,
        recursive=link_to_recursive,
        max_distance=link_to_max_distance,
    )
    if link_to_row:
        filters["link_to"] = link_to_row
    linked_by_row = _build_link_filter_record(
        linked_by,
        negate=linked_by_negate,
        recursive=linked_by_recursive,
        max_distance=linked_by_max_distance,
    )
    if linked_by_row:
        filters["linked_by"] = linked_by_row

    related_row = _clean_string_list(related)
    if related_row:
        related_payload: dict[str, Any] = {"seeds": related_row}
        if max_distance is not None:
            related_payload["max_distance"] = int(max_distance)
        related_ppr_payload = _coerce_related_ppr_payload(
            related_ppr=related_ppr,
            alpha=related_ppr_alpha,
            max_iter=related_ppr_max_iter,
            tol=related_ppr_tol,
            subgraph_mode=related_ppr_subgraph_mode,
        )
        if related_ppr_payload:
            related_payload["ppr"] = related_ppr_payload
        filters["related"] = related_payload

    mentions_row = _clean_string_list(mentions_of)
    if mentions_row:
        filters["mentions_of"] = mentions_row
    mentioned_by_row = _clean_string_list(mentioned_by_notes)
    if mentioned_by_row:
        filters["mentioned_by_notes"] = mentioned_by_row
    if orphan:
        filters["orphan"] = True
    if tagless:
        filters["tagless"] = True
    if missing_backlink:
        filters["missing_backlink"] = True
    scope_row = _coerce_scope(scope)
    if scope_row is not None:
        filters["scope"] = scope_row
    if max_heading_level is not None:
        filters["max_heading_level"] = int(max_heading_level)
    if max_tree_hops is not None:
        filters["max_tree_hops"] = int(max_tree_hops)
    if collapse_to_doc is not None:
        filters["collapse_to_doc"] = bool(collapse_to_doc)
    edge_types_row = _coerce_edge_types(cast("list[str] | tuple[str, ...] | None", edge_types))
    if edge_types_row:
        filters["edge_types"] = edge_types_row
    if per_doc_section_cap is not None:
        filters["per_doc_section_cap"] = int(per_doc_section_cap)
    if min_section_words is not None:
        filters["min_section_words"] = int(min_section_words)

    payload["filters"] = filters

    if created_after is not None:
        payload["created_after"] = int(created_after)
    if created_before is not None:
        payload["created_before"] = int(created_before)
    if modified_after is not None:
        payload["modified_after"] = int(modified_after)
    if modified_before is not None:
        payload["modified_before"] = int(modified_before)
    validate(payload)
    return payload


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "EdgeType",
    "MatchStrategy",
    "PprSubgraphMode",
    "Scope",
    "SortField",
    "SortOrder",
    "build_options_record",
    "get_schema_id",
    "get_schema_path",
    "get_validator",
    "validate",
]
