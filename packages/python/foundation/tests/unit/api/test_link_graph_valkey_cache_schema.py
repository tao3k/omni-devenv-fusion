"""Tests for omni.foundation.api.link_graph_valkey_cache_schema."""

from __future__ import annotations

import pytest

import omni.foundation.api.link_graph_valkey_cache_schema as cache_schema
from omni.foundation.api.link_graph_valkey_cache_schema import get_schema_id, validate


def _payload() -> dict:
    return {
        "schema_version": "omni.link_graph.valkey_cache_snapshot.v1",
        "schema_fingerprint": "abc123",
        "root": "/tmp/notebook",
        "include_dirs": ["docs"],
        "excluded_dirs": [".git", ".cache"],
        "fingerprint": {
            "note_count": 1,
            "latest_modified_ts": 1739980800,
            "total_size_bytes": 42,
        },
        "docs_by_id": {
            "docs/note": {
                "id": "docs/note",
                "id_lower": "docs/note",
                "stem": "note",
                "stem_lower": "note",
                "path": "docs/note.md",
                "path_lower": "docs/note.md",
                "title": "Note",
                "title_lower": "note",
                "tags": [],
                "tags_lower": [],
                "lead": "",
                "word_count": 0,
                "search_text": "",
                "search_text_lower": "",
                "created_ts": None,
                "modified_ts": 1739980800,
            }
        },
        "sections_by_doc": {
            "docs/note": [
                {
                    "heading_path": "Root",
                    "heading_path_lower": "root",
                    "heading_level": 1,
                    "section_text": "hello",
                    "section_text_lower": "hello",
                }
            ]
        },
        "alias_to_doc_id": {"note": "docs/note"},
        "outgoing": {"docs/note": []},
        "incoming": {"docs/note": []},
        "rank_by_id": {"docs/note": 0.0},
        "edge_count": 0,
    }


def test_get_schema_id() -> None:
    schema_id = get_schema_id()
    assert schema_id.endswith("/omni.link_graph.valkey_cache_snapshot.v1.schema.json")


def test_validate_accepts_payload() -> None:
    payload = _payload()
    validate(payload)


def test_validate_rejects_invalid_schema_version() -> None:
    payload = _payload()
    payload["schema_version"] = "omni.link_graph.valkey_cache_snapshot.v0"
    with pytest.raises(ValueError, match="schema_version"):
        validate(payload)


def test_get_validator_raises_when_schema_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_schema.get_validator.cache_clear()
    missing_path = tmp_path / "missing.schema.json"
    monkeypatch.setattr(cache_schema, "get_schema_path", lambda: missing_path)
    with pytest.raises(FileNotFoundError, match="LinkGraph Valkey cache schema not found"):
        cache_schema.get_validator()
    cache_schema.get_validator.cache_clear()
