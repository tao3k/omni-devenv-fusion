"""Versioned loading for built-in pipeline tool contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


BUILTIN_CONTRACTS_VERSION = "v1"


@lru_cache(maxsize=1)
def load_builtin_tool_contracts() -> dict[str, set[str]]:
    """Load built-in tool contracts from versioned JSON resource."""
    filename = f"contracts.{BUILTIN_CONTRACTS_VERSION}.json"
    text = resources.files("omni.tracer.contracts").joinpath(filename).read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("Built-in tool contracts must be a JSON object")
    tool_contracts = raw.get("tool_contracts", {})
    if not isinstance(tool_contracts, dict):
        raise ValueError("Built-in tool contracts must define `tool_contracts` object")

    parsed: dict[str, set[str]] = {}
    for tool_name, cfg in tool_contracts.items():
        if not isinstance(tool_name, str):
            continue
        if not isinstance(cfg, dict):
            continue
        required = cfg.get("required_input_keys", [])
        if not isinstance(required, list):
            continue
        parsed[tool_name] = {item for item in required if isinstance(item, str) and item}
    return parsed


__all__ = [
    "BUILTIN_CONTRACTS_VERSION",
    "load_builtin_tool_contracts",
]
