"""Canonical schema contracts for Rust <-> Python vector payloads."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

HYBRID_SCHEMA_V1 = "omni.vector.hybrid.v1"
VECTOR_SCHEMA_V1 = "omni.vector.search.v1"
TOOL_SEARCH_SCHEMA_V1 = "omni.vector.tool_search.v1"
_TOOL_SEARCH_COMMON_SCHEMA = "omni.vector.tool_search.v1.schema.json"
_VECTOR_COMMON_SCHEMA = "omni.vector.search.v1.schema.json"
_HYBRID_COMMON_SCHEMA = "omni.vector.hybrid.v1.schema.json"


class HybridPayload(BaseModel):
    """Canonical hybrid payload emitted by Rust bindings."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = "hybrid"
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    schema_version: str = Field(alias="schema")

    @classmethod
    def parse_raw_json(cls, raw: str) -> HybridPayload:
        data = json.loads(raw)
        obj = cls.model_validate(data)
        if obj.schema_version != HYBRID_SCHEMA_V1:
            raise ValueError(f"Unsupported hybrid schema: {obj.schema_version}")
        return obj

    def to_search_result_fields(self) -> tuple[str, str, dict[str, Any], float]:
        metadata = dict(self.metadata)
        if self.vector_score is not None or self.keyword_score is not None:
            metadata["debug_scores"] = {
                "vector_score": self.vector_score,
                "keyword_score": self.keyword_score,
            }
        return self.id, self.content, metadata, float(self.score)


class VectorPayload(BaseModel):
    """Canonical vector payload consumed by Python service layer."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    distance: float
    score: float | None = None
    schema_version: str = Field(alias="schema")

    @classmethod
    def parse_raw_json(cls, raw: str) -> VectorPayload:
        data = json.loads(raw)
        obj = cls.model_validate(data)
        if obj.schema_version != VECTOR_SCHEMA_V1:
            raise ValueError(f"Unsupported vector schema: {obj.schema_version}")
        return obj

    def to_search_result_fields(self) -> tuple[str, str, dict[str, Any], float]:
        return self.id, self.content, dict(self.metadata), float(self.distance)


class ToolSearchPayload(BaseModel):
    """Canonical tool-search payload emitted by Rust bindings."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    schema_version: str = Field(alias="schema")
    name: str = Field(min_length=1)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    final_score: float
    confidence: Literal["high", "medium", "low"]
    skill_name: str = ""
    tool_name: str = Field(min_length=1)
    file_path: str = ""
    routing_keywords: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    category: str = ""

    @field_validator("input_schema", mode="before")
    @classmethod
    def _normalize_input_schema(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception:
                return {}
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                try:
                    reparsed = json.loads(parsed)
                except Exception:
                    return {}
                if isinstance(reparsed, dict):
                    return reparsed
            return {}
        return {}

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ToolSearchPayload:
        obj = cls.model_validate(data)
        if obj.schema_version != TOOL_SEARCH_SCHEMA_V1:
            raise ValueError(f"Unsupported tool search schema: {obj.schema_version}")
        return obj

    def to_router_result(self) -> dict[str, Any]:
        full_tool_name = self.tool_name.strip()
        if "." not in full_tool_name and self.skill_name:
            full_tool_name = f"{self.skill_name}.{full_tool_name}"
        if not full_tool_name:
            full_tool_name = self.name
        command = (
            ".".join(full_tool_name.split(".")[1:]) if "." in full_tool_name else full_tool_name
        )
        result = {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "score": float(self.score),
            "final_score": float(self.final_score),
            "confidence": self.confidence,
            "skill_name": self.skill_name,
            "tool_name": full_tool_name,
            "command": command,
            "file_path": self.file_path,
            "routing_keywords": list(self.routing_keywords),
            "intents": list(self.intents),
            "category": self.category,
            "schema": self.schema_version,
            "payload": {
                "skill_name": self.skill_name,
                "command": command,
                "type": "command",
                "description": self.description,
                "tool_name": full_tool_name,
                "input_schema": dict(self.input_schema),
                "metadata": {
                    "skill_name": self.skill_name,
                    "command": command,
                    "tool_name": full_tool_name,
                    "file_path": self.file_path,
                    "routing_keywords": list(self.routing_keywords),
                    "intents": list(self.intents),
                    "category": self.category,
                    "input_schema": dict(self.input_schema),
                },
            },
        }
        if self.vector_score is not None:
            result["vector_score"] = float(self.vector_score)
        if self.keyword_score is not None:
            result["keyword_score"] = float(self.keyword_score)
        return result


class ToolRouterMetadata(BaseModel):
    """Canonical metadata payload consumed by router/CLI output."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str = ""
    command: str = ""
    tool_name: str = ""
    file_path: str = ""
    routing_keywords: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    category: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolRouterPayload(BaseModel):
    """Canonical nested payload for route-test JSON output."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str = ""
    command: str = ""
    type: Literal["command"] = "command"
    description: str = ""
    tool_name: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: ToolRouterMetadata


class ToolRouterResult(BaseModel):
    """Canonical router result passed to CLI and downstream orchestrators."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = ""
    score: float
    confidence: Literal["high", "medium", "low"]
    final_score: float
    skill_name: str = ""
    tool_name: str = ""
    command: str = ""
    file_path: str = ""
    routing_keywords: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    payload: ToolRouterPayload


def build_tool_router_result(payload: ToolSearchPayload, full_tool_name: str) -> dict[str, Any]:
    """Build canonical router result dict from validated tool-search payload."""
    command = ".".join(full_tool_name.split(".")[1:]) if "." in full_tool_name else full_tool_name
    result = ToolRouterResult(
        id=payload.name,
        description=payload.description,
        score=float(payload.score),
        confidence=payload.confidence,
        final_score=float(payload.final_score),
        skill_name=payload.skill_name,
        tool_name=full_tool_name,
        command=command,
        file_path=payload.file_path,
        routing_keywords=list(payload.routing_keywords),
        input_schema=dict(payload.input_schema),
        payload=ToolRouterPayload(
            skill_name=payload.skill_name,
            command=command,
            type="command",
            description=payload.description,
            tool_name=full_tool_name,
            input_schema=dict(payload.input_schema),
            metadata=ToolRouterMetadata(
                skill_name=payload.skill_name,
                command=command,
                tool_name=full_tool_name,
                file_path=payload.file_path,
                routing_keywords=list(payload.routing_keywords),
                intents=list(payload.intents),
                category=payload.category,
                input_schema=dict(payload.input_schema),
            ),
        ),
    )
    return result.model_dump()


class SearchOptionsContract(BaseModel):
    """Contract for scanner tuning options passed to Rust search_optimized."""

    model_config = ConfigDict(extra="forbid")

    where_filter: str | None = Field(
        default=None,
        description="SQL-like Lance filter or serialized JSON metadata filter expression.",
    )
    batch_size: int | None = Field(
        default=None,
        ge=1,
        le=65_536,
        description="Scanner batch size. Effective Rust default is 1024 when omitted.",
    )
    fragment_readahead: int | None = Field(
        default=None,
        ge=1,
        le=256,
        description="Fragments prefetched per scan. Effective Rust default is 4 when omitted.",
    )
    batch_readahead: int | None = Field(
        default=None,
        ge=1,
        le=1024,
        description="Batches prefetched per scan. Effective Rust default is 16 when omitted.",
    )
    scan_limit: int | None = Field(
        default=None,
        ge=1,
        le=1_000_000,
        description="Hard cap on scanned candidates before post-processing.",
    )

    def to_options_json(self) -> str | None:
        """Serialize only explicitly provided options for Rust binding."""
        payload = self.model_dump(exclude_none=True)
        if not payload:
            return None
        return json.dumps(payload, sort_keys=True)


def get_search_options_schema() -> dict[str, Any]:
    """Return canonical JSON Schema for SearchOptionsContract."""
    return SearchOptionsContract.model_json_schema()


def render_search_options_contract_markdown() -> str:
    """Render the docs page for vector search options from schema source of truth."""
    schema = json.dumps(get_search_options_schema(), indent=2, ensure_ascii=False)
    return f"""# Vector Search Options Contract

_This file is auto-generated from `SearchOptionsContract` in `vector_schema.py`._

This document defines the external contract for scanner tuning options passed from Python to Rust via `search_optimized(...)`.

## Scope

- Python entrypoint: `VectorStoreClient.search(...)`
- Rust binding: `PyVectorStore.search_optimized(table_name, query, limit, options_json)`
- Rust runtime: `omni-vector::SearchOptions`

## JSON Schema

```json
{schema}
```

## Request-Level Constraints

- `n_results` range: `1..=1000`
- `collection` must be non-empty

If validation fails, Python returns an empty result list and does not call Rust.

## Recommended Profiles

- `small` (local/dev, <=100k rows): `batch_size=256`, `fragment_readahead=2`, `batch_readahead=4`
- `medium` (default balanced): `batch_size=1024`, `fragment_readahead=4`, `batch_readahead=16`
- `large` (throughput oriented): `batch_size=2048`, `fragment_readahead=8`, `batch_readahead=32`, optionally set `scan_limit`

Start from `medium`, then benchmark against your dataset/query mix before raising readahead.

## Effective Defaults

When a field is omitted (or all options are omitted), Rust applies defaults from `SearchOptions::default()`:

- `batch_size = 1024`
- `fragment_readahead = 4`
- `batch_readahead = 16`
- `scan_limit = None` (uses ANN fetch count)

## Canonical Example

```json
{{
  "where_filter": "{{\\"name\\":\\"tool.echo\\"}}",
  "batch_size": 512,
  "fragment_readahead": 2,
  "batch_readahead": 8,
  "scan_limit": 64
}}
```

## Error Codes (Service Layer)

- `VECTOR_REQUEST_VALIDATION`: invalid request inputs (`n_results`, `collection`, option ranges)
- `VECTOR_BINDING_API_MISSING`: Rust binding missing required method (`search_optimized`)
- `VECTOR_PAYLOAD_VALIDATION`: Rust payload/schema mismatch in vector search response
- `VECTOR_TABLE_NOT_FOUND`: requested collection/table does not exist
- `VECTOR_RUNTIME_ERROR`: unexpected runtime failure in vector search
- `VECTOR_HYBRID_PAYLOAD_VALIDATION`: payload/schema mismatch in hybrid search response
- `VECTOR_HYBRID_TABLE_NOT_FOUND`: requested collection/table does not exist for hybrid search
- `VECTOR_HYBRID_RUNTIME_ERROR`: unexpected runtime failure in hybrid search

## CI Performance Thresholds by OS

The perf guard test (`test_search_perf_guard`) reads thresholds from environment variables:

- `OMNI_VECTOR_PERF_P95_MS`
- `OMNI_VECTOR_PERF_RATIO_MAX`

Current CI matrix values:

- `ubuntu-latest`: `OMNI_VECTOR_PERF_P95_MS=700`, `OMNI_VECTOR_PERF_RATIO_MAX=4.0`
- `macos-latest`: `OMNI_VECTOR_PERF_P95_MS=900`, `OMNI_VECTOR_PERF_RATIO_MAX=4.5`

Only performance guardrails differ by OS. API/schema/default behavior remains cross-platform identical.
"""


def parse_hybrid_payload(raw: str) -> HybridPayload:
    """Parse canonical hybrid payload or raise ValidationError/ValueError."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "keywords" in data:
            raise ValueError(
                "Legacy field 'keywords' is not allowed; use 'routing_keywords' in tool_search only"
            )
        schema_value = data.get("schema")
        if schema_value is not None and schema_value != HYBRID_SCHEMA_V1:
            raise ValueError(f"Unsupported hybrid schema: {schema_value}")
        payload = HybridPayload.model_validate(data)
        _validate_common_schema(_HYBRID_COMMON_SCHEMA, data)
        return payload
    except ValidationError:
        raise
    except ValueError:
        raise


def parse_vector_payload(raw: str) -> VectorPayload:
    """Parse canonical vector payload or raise ValidationError/ValueError."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "keywords" in data:
            raise ValueError(
                "Legacy field 'keywords' is not allowed; use 'routing_keywords' in tool_search only"
            )
        schema_value = data.get("schema")
        if schema_value is not None and schema_value != VECTOR_SCHEMA_V1:
            raise ValueError(f"Unsupported vector schema: {schema_value}")
        payload = VectorPayload.model_validate(data)
        _validate_common_schema(_VECTOR_COMMON_SCHEMA, data)
        return payload
    except ValidationError:
        raise
    except ValueError:
        raise


def parse_tool_search_payload(raw: dict[str, Any]) -> ToolSearchPayload:
    """Parse canonical tool-search payload or raise ValidationError/ValueError."""
    try:
        if "keywords" in raw:
            raise ValueError("Legacy field 'keywords' is not allowed; use 'routing_keywords'")
        schema_value = raw.get("schema")
        if schema_value is not None and schema_value != TOOL_SEARCH_SCHEMA_V1:
            raise ValueError(f"Unsupported tool search schema: {schema_value}")
        canonical_keys = set(ToolSearchPayload.model_fields.keys())
        for field in ToolSearchPayload.model_fields.values():
            if field.alias is not None:
                canonical_keys.add(field.alias)
        canonical = {k: raw[k] for k in canonical_keys if k in raw}
        _validate_tool_search_common_schema(canonical)
        return ToolSearchPayload.from_mapping(canonical)
    except ValidationError:
        raise
    except ValueError:
        raise


def _tool_search_common_schema_path() -> Path:
    return _common_schema_path(_TOOL_SEARCH_COMMON_SCHEMA)


@lru_cache(maxsize=1)
def _tool_search_common_validator() -> Draft202012Validator:
    return _common_schema_validator(_TOOL_SEARCH_COMMON_SCHEMA)


def _validate_tool_search_common_schema(raw: dict[str, Any]) -> None:
    validator = _tool_search_common_validator()
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "<root>"
    raise ValueError(f"Common schema validation failed at {location}: {first.message}")


def _common_schema_path(schema_name: str) -> Path:
    from omni.foundation.config.paths import get_config_paths

    project_root = get_config_paths().project_root
    return project_root / "packages" / "shared" / "schemas" / schema_name


@lru_cache(maxsize=8)
def _common_schema_validator(schema_name: str) -> Draft202012Validator:
    schema_path = _common_schema_path(schema_name)
    if not schema_path.exists():
        raise ValueError(f"Common schema not found: {schema_path}")
    return Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))


def _validate_common_schema(schema_name: str, raw: dict[str, Any]) -> None:
    validator = _common_schema_validator(schema_name)
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "<root>"
    raise ValueError(f"Common schema validation failed at {location}: {first.message}")


def parse_tool_router_result(raw: dict[str, Any]) -> ToolRouterResult:
    """Parse canonical router result payload or raise ValidationError."""
    try:
        return ToolRouterResult.model_validate(raw)
    except ValidationError:
        raise


def build_search_options_json(options: dict[str, Any]) -> str | None:
    """Validate scanner options and return canonical JSON payload."""
    contract = SearchOptionsContract.model_validate(options)
    return contract.to_options_json()


def validate_vector_table_contract(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Check that no entry has legacy 'keywords' in metadata (contract: use routing_keywords only).

    Intended for post-reindex checks and omni db validate-schema. Entries are typically
    the list returned by RustVectorStore.list_all(table_name) (each item = row metadata + id, content).

    Returns:
        Dict with total, legacy_keywords_count, and sample_ids (up to 5) for auditing.
    """
    total = len(entries)
    legacy = [e for e in entries if e.get("keywords") is not None]
    sample_ids = [e.get("id", "") for e in legacy[:5]]
    return {
        "total": total,
        "legacy_keywords_count": len(legacy),
        "sample_ids": sample_ids,
    }


__all__ = [
    "HYBRID_SCHEMA_V1",
    "TOOL_SEARCH_SCHEMA_V1",
    "VECTOR_SCHEMA_V1",
    "HybridPayload",
    "SearchOptionsContract",
    "ToolRouterMetadata",
    "ToolRouterPayload",
    "ToolRouterResult",
    "ToolSearchPayload",
    "build_tool_router_result",
    "VectorPayload",
    "build_search_options_json",
    "get_search_options_schema",
    "parse_hybrid_payload",
    "parse_tool_router_result",
    "parse_tool_search_payload",
    "parse_vector_payload",
    "render_search_options_contract_markdown",
    "validate_vector_table_contract",
]
