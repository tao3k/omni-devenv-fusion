"""JSON payload codecs for Rust binding interop."""

from __future__ import annotations

import json
from typing import Any


def decode_json_object(raw: Any) -> dict[str, Any]:
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON object payload from Wendao engine") from exc
    if not isinstance(payload, dict):
        raise ValueError("Expected object payload from Wendao engine")
    return payload


def decode_json_list(raw: Any) -> list[dict[str, Any]]:
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON list payload from Wendao engine") from exc
    if not isinstance(payload, list):
        raise ValueError("Expected list payload from Wendao engine")
    out: list[dict[str, Any]] = []
    for row in payload:
        if isinstance(row, dict):
            out.append(row)
    return out


__all__ = [
    "decode_json_list",
    "decode_json_object",
]
