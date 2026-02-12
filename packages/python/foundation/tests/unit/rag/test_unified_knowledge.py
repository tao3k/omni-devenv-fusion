"""
Tests for unified_knowledge module.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path


class TestUnifiedEntity:
    """Test UnifiedEntity class."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        from omni.rag.unified_knowledge import UnifiedEntity

        entity = UnifiedEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
        )

        assert entity.name == "Python"
        assert entity.entity_type == "SKILL"

    def test_to_zk_content(self):
        """Test zk content generation."""
        from omni.rag.unified_knowledge import UnifiedEntity

        entity = UnifiedEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
            aliases=["py"],
        )

        content = entity.to_zk_content()

        assert "# Python" in content
        assert "**Type**: SKILL" in content
        assert "#skill" in content


class TestUnifiedKnowledgeManager:
    """Test UnifiedKnowledgeManager class."""

    def test_manager_initialization(self):
        """Test manager can be initialized."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")
        assert manager.notebook_dir == Path("/tmp/test")

    def test_add_entity(self):
        """Test adding entity."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")
        manager.zk_client = MagicMock()

        # Mock existing search to return empty (new entity)
        manager.zk_client.search_notes.return_value = []

        # Mock note creation
        mock_note = MagicMock()
        mock_note.filename_stem = "python"
        mock_note.created = None
        mock_note.modified = None
        manager.zk_client.create_note.return_value = mock_note

        entity = manager.add_entity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
        )

        assert entity is not None
        assert entity.name == "Python"
        assert entity.entity_type == "SKILL"
        manager.zk_client.create_note.assert_called()

    def test_add_entity_already_exists(self):
        """Test adding entity that already exists."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")
        manager.zk_client = MagicMock()

        # Mock existing note
        mock_note = MagicMock()
        mock_note.filename_stem = "python"
        mock_note.title = "Python"
        mock_note.created = None
        mock_note.modified = None
        manager.zk_client.search_notes.return_value = [mock_note]

        entity = manager.add_entity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
        )

        assert entity is not None
        assert entity.zk_note_id == "python"
        # Should not create new note
        manager.zk_client.create_note.assert_not_called()


class TestSearch:
    """Test search functionality."""

    def test_search_with_mock(self):
        """Test search returns results."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")

        # Mock zk
        mock_note = MagicMock()
        mock_note.title = "Python"
        mock_note.path = "python.md"
        mock_note.lead = "About Python"
        mock_note.body = ""
        mock_note.tags = ["skill"]

        manager.zk_client = MagicMock()
        manager.zk_client.search_notes.return_value = [mock_note]

        results = manager.search("python")

        assert "notes" in results
        assert len(results["notes"]) == 1
        assert results["notes"][0]["title"] == "Python"


class TestGetStats:
    """Test statistics functionality."""

    def test_get_stats(self):
        """Test getting stats."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")

        manager.zk_client = MagicMock()
        manager.zk_client.get_stats.return_value = {
            "total_notes": 20,
        }

        stats = manager.get_stats()

        assert "total_notes" in stats
        assert stats["total_notes"] == 20


class TestConvenienceFunction:
    """Test convenience functions."""

    def test_get_unified_manager(self):
        """Test getting unified manager."""
        from omni.rag.unified_knowledge import get_unified_manager

        manager = get_unified_manager("/custom/path")

        assert manager is not None
        assert manager.notebook_dir == Path("/custom/path")


class TestListByTag:
    """Test list by tag functionality."""

    def test_list_by_tag(self):
        """Test listing notes by tag."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")

        mock_note = MagicMock()
        mock_note.title = "Python"
        mock_note.path = "python.md"
        mock_note.lead = "About Python"
        mock_note.body = ""
        mock_note.tags = ["skill"]

        manager.zk_client = MagicMock()
        manager.zk_client.search_notes.return_value = [mock_note]

        results = manager.list_by_tag("skill")

        assert len(results) == 1
        assert results[0]["title"] == "Python"


class TestGetGraph:
    """Test get graph functionality."""

    def test_get_graph(self):
        """Test getting graph."""
        from omni.rag.unified_knowledge import UnifiedKnowledgeManager

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test")

        manager.zk_client = MagicMock()
        manager.zk_client.get_graph.return_value = {
            "nodes": [{"id": "python", "type": "skill"}],
            "links": [],
        }

        graph = manager.get_graph()

        assert "nodes" in graph
        assert len(graph["nodes"]) == 1
