"""
test_invoker_stack.py - Unit tests for create_default_invoker_stack helper.
"""

from __future__ import annotations

import pytest

from omni.tracer import create_default_invoker_stack


class _MCPClient:
    async def call_tool(self, name: str, arguments: dict | None = None):
        return {"source": "mcp", "name": name, "arguments": arguments or {}}


@pytest.mark.asyncio
async def test_default_stack_uses_mapping_when_available():
    async def mapped(payload, state):
        return {"source": "mapping", "payload": payload}

    invoker = create_default_invoker_stack(
        include_retrieval=False,
        mapping={"demo.run": mapped},
    )
    out = await invoker.invoke("demo", "run", {"x": 1}, {})
    assert out["source"] == "mapping"
    assert out["payload"]["x"] == 1


@pytest.mark.asyncio
async def test_default_stack_prioritizes_mcp_over_mapping():
    async def mapped(payload, state):
        return {"source": "mapping"}

    invoker = create_default_invoker_stack(
        mcp_client=_MCPClient(),
        include_retrieval=False,
        mapping={"demo.run": mapped},
    )
    out = await invoker.invoke("demo", "run", {"x": 1}, {})
    assert out["source"] == "mcp"
    assert out["name"] == "demo.run"


@pytest.mark.asyncio
async def test_default_stack_falls_back_to_noop():
    invoker = create_default_invoker_stack(include_retrieval=False, mapping={})
    out = await invoker.invoke("unknown", "tool", {}, {})
    assert out["status"] == "completed"
    assert out["server"] == "unknown"
    assert out["tool"] == "tool"


@pytest.mark.asyncio
async def test_default_stack_can_include_retrieval(monkeypatch):
    import omni.tracer.invoker_stack as module

    class _FakeRetrievalInvoker:
        def __init__(self, default_backend: str = "lance"):
            self.default_backend = default_backend

        async def invoke(self, server, tool, payload, state):
            if server == "retriever" and tool == "search":
                return {"source": "retrieval", "count": 1, "backend": self.default_backend}
            return {"status": "not_implemented"}

    monkeypatch.setattr(module, "RetrievalToolInvoker", _FakeRetrievalInvoker)
    invoker = module.create_default_invoker_stack(
        include_retrieval=True,
        retrieval_default_backend="hybrid",
        mapping={},
    )
    out = await invoker.invoke("retriever", "search", {"query": "typed"}, {})
    assert out["source"] == "retrieval"
    assert out["count"] == 1
    assert out["backend"] == "hybrid"
