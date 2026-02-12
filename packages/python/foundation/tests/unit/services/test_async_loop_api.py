"""Guardrails for modern asyncio loop APIs in foundation services."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_foundation_services_use_get_running_loop() -> None:
    files = [
        "packages/python/foundation/src/omni/foundation/bridge/rust_vector.py",
        "packages/python/foundation/src/omni/foundation/services/llm/provider.py",
    ]

    for file_path in files:
        content = _read(file_path)
        assert "asyncio.get_event_loop()" not in content
        assert "asyncio.get_running_loop()" in content
