"""
MCP tool result schema API – single place for packages/shared/schemas/omni.mcp.tool_result.v1.

Load, validate, and build payloads that conform to the shared schema so MCP clients
(e.g. Cursor) never see result: null or invalid_union.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# SSOT: packages/shared/schemas/omni.mcp.tool_result.v1.schema.json
SCHEMA_NAME = "omni.mcp.tool_result.v1.schema.json"
CONTENT_KEY = "content"
IS_ERROR_KEY = "isError"


def get_schema_path() -> Path:
    """Path to the shared MCP tool result schema file."""
    from omni.foundation.config.paths import get_config_paths

    return get_config_paths().project_root / "packages" / "shared" / "schemas" / SCHEMA_NAME


@lru_cache(maxsize=1)
def get_validator() -> Draft202012Validator:
    """Cached validator for the MCP tool result schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"MCP tool result schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload does not conform to the shared schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"MCP tool result schema violation at {loc}: {first.message}")


def build_result(text: str, is_error: bool = False) -> dict[str, Any]:
    """Build a payload that conforms to the shared schema."""
    out = {
        CONTENT_KEY: [{"type": "text", "text": text}],
        IS_ERROR_KEY: is_error,
    }
    if get_schema_path().exists():
        validate(out)
    return out


def is_canonical(value: Any) -> bool:
    """True if value is already a valid MCP tool result shape."""
    if not isinstance(value, dict) or CONTENT_KEY not in value or IS_ERROR_KEY not in value:
        return False
    content = value[CONTENT_KEY]
    if not isinstance(content, list):
        return False
    if not content:
        return False
    item = content[0]
    return isinstance(item, dict) and item.get("type") == "text" and "text" in item


__all__ = [
    "SCHEMA_NAME",
    "CONTENT_KEY",
    "IS_ERROR_KEY",
    "get_schema_path",
    "get_validator",
    "validate",
    "build_result",
    "is_canonical",
]
