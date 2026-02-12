"""
test_mcp_invoker.py - Unit tests for MCPToolInvoker.

Validates:
- Compatibility with multiple call_tool signatures
- MCP response normalization
- Integration with pipeline-generated LangGraph nodes
"""

from __future__ import annotations

import pytest

from omni.tracer import MCPToolInvoker, PipelineConfig, create_langgraph_from_pipeline


class _ClientPositional:
    async def call_tool(self, name: str, arguments: dict | None = None):
        assert name == "retriever.search"
        assert arguments == {"query": "typed languages"}
        return {"docs": ["d1", "d2"], "status": "ok"}


class _ClientKeyword:
    async def call_tool(self, name: str, **kwargs):
        assert name == "retriever.search"
        assert kwargs == {"query": "typed languages"}
        return {"docs": ["k1"], "status": "ok"}


class _ClientTextList:
    async def call_tool(self, name: str, arguments: dict | None = None):
        assert name == "retriever.search"
        assert arguments == {"query": "typed languages"}
        return [{"type": "text", "text": '{"docs":["j1","j2"],"status":"ok"}'}]


@pytest.mark.asyncio
async def test_mcp_invoker_supports_positional_arguments_signature():
    invoker = MCPToolInvoker(_ClientPositional())
    result = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed languages"},
        state={},
    )
    assert result["docs"] == ["d1", "d2"]


@pytest.mark.asyncio
async def test_mcp_invoker_supports_keyword_signature():
    invoker = MCPToolInvoker(_ClientKeyword())
    result = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed languages"},
        state={},
    )
    assert result["docs"] == ["k1"]


@pytest.mark.asyncio
async def test_mcp_invoker_normalizes_text_content_json():
    invoker = MCPToolInvoker(_ClientTextList())
    result = await invoker.invoke(
        server="retriever",
        tool="search",
        payload={"query": "typed languages"},
        state={},
    )
    assert result["docs"] == ["j1", "j2"]


@pytest.mark.asyncio
async def test_mcp_invoker_integrates_with_pipeline_graph():
    config = PipelineConfig(
        servers={"retriever": "/unused"},
        pipeline=[
            {
                "retriever.search": {
                    "input": {"query": "$query"},
                    "output": ["docs"],
                }
            }
        ],
    )
    app = create_langgraph_from_pipeline(
        config,
        state_schema=dict,
        tool_invoker=MCPToolInvoker(_ClientPositional()),
    )
    result = await app.ainvoke({"query": "typed languages"})
    assert result["docs"] == ["d1", "d2"]
