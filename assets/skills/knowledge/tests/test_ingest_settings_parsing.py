"""Tests for ingest_document setting parsing through shared runtime helpers."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _import_graph_module():
    import graph as graph_mod

    return graph_mod


def _unwrap_skill_output(payload: Any) -> dict[str, Any]:
    """Unwrap skill_command response payload into parsed JSON dict."""
    if isinstance(payload, str):
        return json.loads(payload)
    if isinstance(payload, dict):
        content = payload.get("content") or []
        if content and isinstance(content[0], dict):
            text = content[0].get("text", "")
            if isinstance(text, str):
                return json.loads(text)
    raise AssertionError(f"Unexpected payload shape: {type(payload)!r}")


@pytest.mark.asyncio
async def test_ingest_document_uses_typed_runtime_setting_resolvers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ingest should parse bool/int settings correctly from string config values."""
    graph = _import_graph_module()
    source = tmp_path / "ingest.md"
    source.write_text("seed content", encoding="utf-8")

    parser_calls: dict[str, Any] = {}
    chunk_calls: dict[str, Any] = {}
    vector_calls: dict[str, Any] = {}

    class _FakeRagConfig:
        def is_enabled(self, _name: str) -> bool:
            return True

    class _FakeParser:
        async def parse(
            self,
            _path: str,
            *,
            max_workers: int,
            fast_path_for_pdf: bool,
        ) -> list[dict[str, str]]:
            parser_calls["max_workers"] = max_workers
            parser_calls["fast_path_for_pdf"] = fast_path_for_pdf
            return [{"text": "alpha beta gamma"}]

    class _FakeVectorStore:
        store = object()

        async def delete_by_metadata_source(self, *, collection: str, source: str) -> int:
            vector_calls["delete_collection"] = collection
            vector_calls["delete_source"] = source
            return 0

        async def add_batch(
            self,
            texts: list[str],
            metas: list[dict[str, Any]],
            *,
            collection: str,
            batch_size: int,
            max_concurrent_embed_batches: int,
        ) -> int:
            vector_calls["collection"] = collection
            vector_calls["batch_size"] = batch_size
            vector_calls["parallel_batches"] = max_concurrent_embed_batches
            vector_calls["texts"] = list(texts)
            vector_calls["metas"] = list(metas)
            return len(texts)

    fake_vector = _FakeVectorStore()

    def _fake_get_setting(key: str, default: Any = None) -> Any:
        values = {
            "knowledge.ingest_parse_max_workers": "3",
            "knowledge.ingest_pdf_fast_path": "false",
            "knowledge.ingest_extract_images": "false",
            "knowledge.ingest_chunk_target_tokens": "128",
            "knowledge.ingest_chunk_overlap_tokens": "16",
            "knowledge.ingest_embed_batch_size": "7",
            "knowledge.ingest_embed_parallel_batches": "5",
            "knowledge.ingest_graph_parallel_writes": "false",
        }
        return values.get(key, default)

    def _fake_chunk_text(
        _text: str,
        *,
        chunk_size_tokens: int,
        overlap_tokens: int,
    ) -> list[tuple[str, int]]:
        chunk_calls["chunk_size_tokens"] = chunk_size_tokens
        chunk_calls["overlap_tokens"] = overlap_tokens
        return [("chunk-a", 0), ("chunk-b", 1)]

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)
    monkeypatch.setattr("omni.rag.config.get_rag_config", lambda: _FakeRagConfig())
    monkeypatch.setattr("omni.rag.document.DocumentParser", _FakeParser)
    monkeypatch.setattr("omni.foundation.get_vector_store", lambda: fake_vector)
    monkeypatch.setitem(
        sys.modules,
        "omni_core_rs",
        SimpleNamespace(py_chunk_text=_fake_chunk_text),
    )

    output = await graph.ingest_document(
        file_path=str(source),
        extract_entities=False,
        store_in_graph=False,
    )
    data = _unwrap_skill_output(output)

    assert parser_calls["max_workers"] == 3
    assert parser_calls["fast_path_for_pdf"] is False
    assert chunk_calls["chunk_size_tokens"] == 128
    assert chunk_calls["overlap_tokens"] == 16
    assert vector_calls["batch_size"] == 7
    assert vector_calls["parallel_batches"] == 5
    assert data["chunks_created"] == 2
    assert data["chunks_stored_in_vector_db"] == 2
