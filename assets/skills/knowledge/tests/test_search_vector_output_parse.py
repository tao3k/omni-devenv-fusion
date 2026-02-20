"""Unit tests for search.vector output parsing."""

from __future__ import annotations

import json
import sys
import types

import pytest
from search.vector import run_vector_search


def _install_recall(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    module = types.ModuleType("recall")

    async def _recall(_query: str, limit: int = 10, collection: str = "knowledge_chunks"):
        del limit, collection
        return payload

    module.recall = _recall
    monkeypatch.setitem(sys.modules, "recall", module)


@pytest.mark.asyncio
async def test_run_vector_search_parses_json_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_recall(monkeypatch, json.dumps({"status": "success", "results": []}))
    out = await run_vector_search("architecture", limit=3)
    assert out["success"] is True
    assert out["status"] == "success"
    assert isinstance(out["results"], list)


@pytest.mark.asyncio
async def test_run_vector_search_parses_skill_command_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_recall(
        monkeypatch,
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"status": "unavailable", "results": []}),
                }
            ],
            "isError": False,
        },
    )
    out = await run_vector_search("architecture", limit=3)
    assert out["success"] is True
    assert out["status"] == "unavailable"


@pytest.mark.asyncio
async def test_run_vector_search_falls_back_to_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_recall(monkeypatch, "not-json")
    out = await run_vector_search("architecture", limit=3)
    assert out["success"] is True
    assert out["raw"] == "not-json"
