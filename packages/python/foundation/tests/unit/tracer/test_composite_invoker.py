"""
test_composite_invoker.py - Unit tests for CompositeToolInvoker.
"""

from __future__ import annotations

import pytest

from omni.tracer import CompositeToolInvoker, MappingToolInvoker, NoOpToolInvoker


class _ErrorInvoker:
    async def invoke(self, server, tool, payload, state):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_composite_invoker_uses_first_implemented_result():
    first = MappingToolInvoker({})

    async def ok(payload, state):
        return {"value": 42}

    second = MappingToolInvoker({"demo.run": ok})
    invoker = CompositeToolInvoker([first, second], default_invoker=NoOpToolInvoker())
    out = await invoker.invoke("demo", "run", {}, {})
    assert out["value"] == 42


@pytest.mark.asyncio
async def test_composite_invoker_handles_errors_and_falls_back():
    invoker = CompositeToolInvoker(
        [_ErrorInvoker(), MappingToolInvoker({})],
        default_invoker=NoOpToolInvoker(),
    )
    out = await invoker.invoke("demo", "missing", {"x": 1}, {})
    assert out["status"] == "completed"
    assert out["server"] == "demo"
    assert out["tool"] == "missing"
    assert "errors" in out
    assert "RuntimeError: boom" in out["errors"][0]
