"""Tests for knowledge CLI command behaviors."""

from __future__ import annotations

import asyncio
import sys
import types
from typing import TYPE_CHECKING

import pytest
import typer

from omni.agent.cli.commands import knowledge as knowledge_module

if TYPE_CHECKING:
    from pathlib import Path


def _module(name: str, **attrs: object) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def test_knowledge_stats_uses_link_graph_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class _FakeBackend:
        async def stats(self) -> dict[str, int]:
            return {
                "total_notes": 9,
                "orphans": 2,
                "links_in_graph": 7,
                "nodes_in_graph": 9,
            }

    monkeypatch.setitem(
        sys.modules,
        "omni.rag.link_graph",
        _module(
            "omni.rag.link_graph", get_link_graph_backend=lambda notebook_dir=None: _FakeBackend()
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "omni.foundation.config.link_graph",
        _module(
            "omni.foundation.config.link_graph",
            get_link_graph_notebook_dir=lambda: tmp_path,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "omni.foundation.utils.asyncio",
        _module("omni.foundation.utils.asyncio", run_async_blocking=lambda coro: asyncio.run(coro)),
    )
    monkeypatch.setattr(
        knowledge_module, "_print_stats", lambda stats: captured.setdefault("stats", stats)
    )

    knowledge_module.knowledge_stats()

    assert captured["stats"] == {
        "total_notes": 9,
        "orphans": 2,
        "links_in_graph": 7,
        "nodes_in_graph": 9,
    }


def test_knowledge_stats_import_error_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "omni.rag.link_graph",
        _module("omni.rag.link_graph"),
    )
    monkeypatch.setitem(
        sys.modules,
        "omni.foundation.config.link_graph",
        _module(
            "omni.foundation.config.link_graph",
            get_link_graph_notebook_dir=lambda: tmp_path,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "omni.foundation.utils.asyncio",
        _module("omni.foundation.utils.asyncio", run_async_blocking=lambda coro: asyncio.run(coro)),
    )

    with pytest.raises(typer.Exit) as exc:
        knowledge_module.knowledge_stats()
    assert exc.value.exit_code == 1
