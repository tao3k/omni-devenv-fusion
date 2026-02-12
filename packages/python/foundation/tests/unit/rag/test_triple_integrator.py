"""
Tests for triple_integrator module.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestTripleEntity:
    """Test TripleEntity class."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        from omni.rag.triple_integrator import TripleEntity

        entity = TripleEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
            aliases=["py", "python3"],
        )

        assert entity.name == "Python"
        assert entity.entity_type == "SKILL"
        assert len(entity.aliases) == 2

    def test_to_zk_content(self):
        """Test zk content generation."""
        from omni.rag.triple_integrator import TripleEntity

        entity = TripleEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
            outgoing=["Rust", "Docker"],
            zk_tags=["programming", "language"],
        )

        content = entity.to_zk_content()

        assert "# Python" in content
        assert "## Links" in content
        assert "[[rust]]" in content
        assert "[[docker]]" in content
        assert "#skill" in content


class TestTripleRelation:
    """Test TripleRelation class."""

    def test_relation_creation(self):
        """Test basic relation creation."""
        from omni.rag.triple_integrator import TripleRelation

        relation = TripleRelation(
            source="Claude Code",
            target="Python",
            relation_type="USES",
            description="Uses Python",
        )

        assert relation.source == "Claude Code"
        assert relation.target == "Python"
        assert relation.relation_type == "USES"


class TestTripleKnowledgeSystem:
    """Test TripleKnowledgeSystem class."""

    def test_initialization(self):
        """Test system initialization."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        assert system.notebook_dir == Path("/tmp/test")
        assert system.zk_client is not None

    def test_extract_from_code(self):
        """Test entity extraction from code."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        code = """
        def hello():
            print("Hello, World!")

        # Uses Python, Docker, and Git
        import os
        """

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")
        entities = system.extract_from_code(code, source_name="test.py")

        # Should find Python, Docker, Git
        entity_names = [e.name.lower() for e in entities]
        assert any("python" in name for name in entity_names)

    def test_extract_from_text(self):
        """Test entity extraction from text."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        text = """
        Our project uses React for the frontend and FastAPI for the backend.
        We deploy with Docker and manage code with Git.
        """

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")
        entities = system.extract_from_text(text, source_name="readme.md")

        # Should find React, FastAPI, Docker, Git
        entity_names = [e.name.lower() for e in entities]
        assert any("react" in name for name in entity_names)
        assert any("fastapi" in name for name in entity_names)

    def test_sync_single_entity(self):
        """Test syncing a single entity."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem, TripleEntity

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        # Create a TripleEntity and add to cache
        entity = TripleEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
        )
        entity.outgoing = []
        entity.zk_tags = []
        system._entity_cache["Python"] = entity

        # Mock zk client
        mock_zk_client = MagicMock()
        mock_note = MagicMock()
        mock_note.filename_stem = "python"
        mock_note.path = "python.md"
        mock_zk_client.create_note.return_value = mock_note
        system.zk_client = mock_zk_client

        result = system.sync_entity("Python")

        # Should call zk create_note
        mock_zk_client.create_note.assert_called()

    def test_query_entities(self):
        """Test querying entities."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        # Mock Rust graph
        mock_entity = MagicMock()
        mock_entity.name = "Python"
        mock_entity.entity_type = "SKILL"
        mock_entity.description = "Programming language"
        mock_entity.aliases = []

        system.rust_graph = MagicMock()
        system.rust_graph.search_entities.return_value = [mock_entity]

        # Mock zk client to prevent real subprocess calls
        mock_zk_client = MagicMock()
        mock_zk_client.search_notes.return_value = []
        system.zk_client = mock_zk_client

        results = system.query_entities("python")

        assert len(results) >= 1
        assert results[0]["name"] == "Python"

    def test_query_notes(self):
        """Test querying notes."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        # Mock zk client
        mock_zk_client = MagicMock()
        mock_note = MagicMock()
        mock_note.title = "Python"
        mock_note.path = "python.md"
        mock_note.lead = "About Python"
        mock_note.body = ""
        mock_note.tags = ["skill"]
        mock_zk_client.search_notes.return_value = [mock_note]
        system.zk_client = mock_zk_client

        results = system.query_notes("python")

        assert len(results) >= 1
        assert results[0]["title"] == "Python"

    def test_get_stats(self):
        """Test getting statistics."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        system.rust_graph = MagicMock()
        system.rust_graph.get_stats.return_value = '{"total_entities": 10}'

        mock_zk_client = MagicMock()
        mock_zk_client.get_stats.return_value = {"total_notes": 20}
        system.zk_client = mock_zk_client

        stats = system.get_stats()

        assert "cached_entities" in stats
        assert "rust_graph" in stats
        assert "zk_notebook" in stats

    def test_clear_cache(self):
        """Test clearing entity cache."""
        from omni.rag.triple_integrator import TripleKnowledgeSystem

        system = TripleKnowledgeSystem(notebook_dir="/tmp/test")

        # Add some entities to cache
        system._entity_cache["Python"] = MagicMock()
        system._entity_cache["Rust"] = MagicMock()

        assert len(system._entity_cache) == 2

        system.clear_cache()

        assert len(system._entity_cache) == 0


class TestConvenienceFunction:
    """Test convenience functions."""

    def test_get_triple_system(self):
        """Test getting triple system."""
        from omni.rag.triple_integrator import get_triple_system

        system = get_triple_system("/custom/path")

        assert system is not None
        assert system.notebook_dir == Path("/custom/path")
