"""
Omni Agent server info schema API – single place for packages/shared/schemas/omni.agent.server_info.v1.

Load, validate, and build payloads for GET /sse, /mcp responses. Unified with project schema validation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# SSOT: packages/shared/schemas/omni.agent.server_info.v1.schema.json
SCHEMA_NAME = "omni.agent.server_info.v1.schema.json"
NAME_KEY = "name"
VERSION_KEY = "version"
PROTOCOL_VERSION_KEY = "protocolVersion"
MESSAGE_KEY = "message"


def get_schema_path() -> Path:
    """Path to the shared agent server info schema file."""
    from omni.foundation.config.paths import get_config_paths

    return get_config_paths().project_root / "packages" / "shared" / "schemas" / SCHEMA_NAME


@lru_cache(maxsize=1)
def get_validator() -> Draft202012Validator:
    """Cached validator for the agent server info schema."""
    path = get_schema_path()
    if not path.exists():
        raise FileNotFoundError(f"Agent server info schema not found: {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def validate(payload: dict[str, Any]) -> None:
    """Raise ValueError if payload does not conform to the shared schema."""
    errs = sorted(get_validator().iter_errors(payload), key=lambda e: list(e.path))
    if not errs:
        return
    first = errs[0]
    loc = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"Agent server info schema violation at {loc}: {first.message}")


def build_server_info(
    name: str = "omni-agent",
    version: str = "2.0.0",
    protocol_version: str = "2024-11-05",
    message: str | None = None,
) -> dict[str, Any]:
    """Build a payload that conforms to the shared schema."""
    out: dict[str, Any] = {
        NAME_KEY: name,
        VERSION_KEY: version,
        PROTOCOL_VERSION_KEY: protocol_version,
    }
    if message is not None:
        out[MESSAGE_KEY] = message
    if get_schema_path().exists():
        validate(out)
    return out


__all__ = [
    "SCHEMA_NAME",
    "NAME_KEY",
    "VERSION_KEY",
    "PROTOCOL_VERSION_KEY",
    "MESSAGE_KEY",
    "get_schema_path",
    "get_validator",
    "validate",
    "build_server_info",
]
