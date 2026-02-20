"""
MCP tool result schema API - single place for packages/shared/schemas/omni.mcp.tool_result.v1.

Load, validate, and build payloads that conform to the shared schema so MCP clients
(e.g. Cursor) never see result: null or invalid_union.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

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


def enforce_result_shape(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a schema-only copy of the payload (content + isError). No extra keys.

    Use after is_canonical() so MCP clients (e.g. Cursor) never receive
    additionalProperties. Validates the stripped payload against the shared schema.
    """
    out = {
        CONTENT_KEY: payload[CONTENT_KEY],
        IS_ERROR_KEY: payload[IS_ERROR_KEY],
    }
    if get_schema_path().exists():
        validate(out)
    return out


def parse_result_payload(value: Any) -> dict[str, Any]:
    """Parse raw/canonical tool result payload into an inner result dict.

    Supports:
    - Raw dict payloads returned by tools.
    - JSON strings containing a dict.
    - Canonical MCP payloads where content[0].text contains JSON.
    """
    if isinstance(value, dict):
        data = value
    elif isinstance(value, str):
        data = json.loads(value)
        if not isinstance(data, dict):
            raise TypeError(f"Expected JSON object payload, got: {type(data).__name__}")
    else:
        raise TypeError(f"Unsupported payload type: {type(value).__name__}")

    if is_canonical(data):
        content = data.get(CONTENT_KEY) or []
        first = content[0] if content else {}
        text = first.get("text") if isinstance(first, dict) else None
        if isinstance(text, str) and text.strip():
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                # Not JSON; keep canonical payload unchanged.
                return data
    return data


def _extract_text_from_content(content: Any) -> str | None:
    """Extract text from MCP content array."""
    if not isinstance(content, list):
        return None
    texts: list[str] = []
    for item in content:
        if isinstance(item, str):
            if item:
                texts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            texts.append(text)
    if not texts:
        return None
    return "\n".join(texts)


def extract_text_content(value: Any) -> str | None:
    """Extract tool text payload across common MCP/JSON-RPC response shapes.

    Supported inputs:
    - JSON-RPC response dict: ``{"result": {...}}`` or ``{"error": {...}}``
    - Canonical MCP tool result: ``{"content":[{"type":"text","text":"..."}],"isError":...}``
    - Raw text dict: ``{"text":"..."}``
    - Content list payloads
    """
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return _extract_text_from_content(value)

    if not isinstance(value, dict):
        return None

    if "result" in value:
        nested = extract_text_content(value.get("result"))
        if nested is not None:
            return nested

    error = value.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
        nested = extract_text_content(error.get("data"))
        if nested is not None:
            return nested

    content_text = _extract_text_from_content(value.get(CONTENT_KEY))
    if content_text is not None:
        return content_text

    text = value.get("text")
    if isinstance(text, str):
        return text

    for key in ("data", "payload", "response"):
        nested = extract_text_content(value.get(key))
        if nested is not None:
            return nested

    return None


__all__ = [
    "CONTENT_KEY",
    "IS_ERROR_KEY",
    "SCHEMA_NAME",
    "build_result",
    "enforce_result_shape",
    "extract_text_content",
    "get_schema_path",
    "get_validator",
    "is_canonical",
    "parse_result_payload",
    "validate",
]
