"""Guardrails for modern asyncio loop APIs in MCP transport."""

from __future__ import annotations

from pathlib import Path


def test_stdio_transport_uses_get_running_loop() -> None:
    path = Path("packages/python/mcp-server/src/omni/mcp/transport/stdio.py")
    content = path.read_text(encoding="utf-8")
    assert "asyncio.get_event_loop()" not in content
    assert content.count("asyncio.get_running_loop()") >= 2
