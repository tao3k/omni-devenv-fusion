"""Tests for versioned built-in tool contract loading."""

from __future__ import annotations

from omni.tracer.pipeline_tool_contracts import (
    BUILTIN_CONTRACTS_VERSION,
    load_builtin_tool_contracts,
)


def test_load_builtin_tool_contracts_from_versioned_resource():
    contracts = load_builtin_tool_contracts()
    assert BUILTIN_CONTRACTS_VERSION == "v1"
    assert "retriever.rerank_passages" not in contracts
    assert contracts["retriever.hybrid_search"] == {"query"}
