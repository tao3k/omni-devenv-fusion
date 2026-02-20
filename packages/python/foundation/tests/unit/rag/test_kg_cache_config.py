"""Tests for KG cache integration: _load_kg, _save_kg via Rust load_kg_from_lance_cached.

Verifies that Python dual_core._config uses the Rust-side KG cache correctly:
- Repeated _load_kg returns consistent results (cache hit)
- _save_kg invalidates cache so next _load_kg sees fresh data
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("omni_core_rs")


class TestLoadKgRustCache:
    """Tests for _load_kg using Rust load_kg_from_lance_cached."""

    def test_load_kg_empty_dir_returns_empty_graph(self, tmp_path):
        """Empty Lance dir returns graph with 0 entities (graceful fallback)."""
        from omni.rag.dual_core._config import _load_kg

        lance_dir = tmp_path / "knowledge.lance"
        lance_dir.mkdir(parents=True)

        kg = _load_kg(lance_dir=str(lance_dir))
        assert kg is not None
        stats = json.loads(kg.get_stats())
        assert stats["total_entities"] == 0
        assert stats["total_relations"] == 0

    def test_load_kg_after_save_returns_graph(self, tmp_path):
        """Create graph, save via _save_kg, load via _load_kg returns same data."""
        from omni_core_rs import PyEntity, PyKnowledgeGraph, PyRelation

        from omni.rag.dual_core._config import _load_kg, _save_kg

        lance_dir = tmp_path / "knowledge.lance"
        lance_dir.mkdir(parents=True)

        kg = PyKnowledgeGraph()
        e = PyEntity(
            name="TestTool",
            entity_type="TOOL",
            description="A test tool for cache verification",
        )
        kg.add_entity(e)
        _save_kg(kg, lance_dir=lance_dir)

        loaded = _load_kg(lance_dir=lance_dir)
        assert loaded is not None
        stats = json.loads(loaded.get_stats())
        assert stats["total_entities"] == 1
        assert stats["total_relations"] == 0

    def test_load_kg_repeated_returns_same(self, tmp_path):
        """Repeated _load_kg with same path returns consistent result (Rust cache hit)."""
        from omni_core_rs import PyEntity, PyKnowledgeGraph

        from omni.rag.dual_core._config import _load_kg, _save_kg

        lance_dir = tmp_path / "knowledge.lance"
        lance_dir.mkdir(parents=True)

        kg = PyKnowledgeGraph()
        kg.add_entity(
            PyEntity(name="CacheTest", entity_type="CONCEPT", description="For cache test")
        )
        _save_kg(kg, lance_dir=lance_dir)

        g1 = _load_kg(lance_dir=lance_dir)
        g2 = _load_kg(lance_dir=lance_dir)
        assert g1 is not None
        assert g2 is not None
        s1 = json.loads(g1.get_stats())
        s2 = json.loads(g2.get_stats())
        assert s1["total_entities"] == s2["total_entities"] == 1

    def test_save_kg_invalidates_cache(self, tmp_path):
        """_save_kg invalidates Rust cache; next _load_kg sees fresh data."""
        from omni_core_rs import PyEntity, PyKnowledgeGraph

        from omni.rag.dual_core._config import _load_kg, _save_kg

        lance_dir = tmp_path / "knowledge.lance"
        lance_dir.mkdir(parents=True)

        # Initial: 1 entity
        kg1 = PyKnowledgeGraph()
        kg1.add_entity(PyEntity(name="First", entity_type="CONCEPT", description="First entity"))
        _save_kg(kg1, lance_dir=lance_dir)

        loaded1 = _load_kg(lance_dir=lance_dir)
        assert loaded1 is not None
        assert json.loads(loaded1.get_stats())["total_entities"] == 1

        # Update: add second entity and save
        kg2 = PyKnowledgeGraph()
        kg2.add_entity(PyEntity(name="First", entity_type="CONCEPT", description="First entity"))
        kg2.add_entity(PyEntity(name="Second", entity_type="CONCEPT", description="Second entity"))
        _save_kg(kg2, lance_dir=lance_dir)

        # Next load must see 2 entities (cache was invalidated)
        loaded2 = _load_kg(lance_dir=lance_dir)
        assert loaded2 is not None
        assert json.loads(loaded2.get_stats())["total_entities"] == 2
