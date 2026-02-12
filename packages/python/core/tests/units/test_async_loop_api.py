"""Guardrails for modern asyncio loop APIs in core modules."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_core_modules_use_get_running_loop() -> None:
    files = [
        "packages/python/core/src/omni/core/router/indexer.py",
        "packages/python/core/src/omni/core/skills/runtime/omni_cell.py",
    ]

    for file_path in files:
        content = _read(file_path)
        assert "asyncio.get_event_loop()" not in content
        assert "asyncio.get_running_loop()" in content
