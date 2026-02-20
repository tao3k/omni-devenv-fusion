"""Tests for unified_knowledge module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from omni.rag.unified_knowledge import UnifiedEntity, UnifiedKnowledgeManager, get_unified_manager


class TestUnifiedEntity:
    """Test UnifiedEntity class."""

    def test_entity_creation(self) -> None:
        entity = UnifiedEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
        )
        assert entity.name == "Python"
        assert entity.entity_type == "SKILL"

    def test_to_note_content(self) -> None:
        entity = UnifiedEntity(
            name="Python",
            entity_type="SKILL",
            description="Programming language",
            aliases=["py"],
        )
        content = entity.to_note_content()
        assert "# Python" in content
        assert "**Type**: SKILL" in content
        assert "#skill" in content


class TestUnifiedKnowledgeManager:
    """Test UnifiedKnowledgeManager class."""

    def _build_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.search_planned = AsyncMock(
            return_value={"query": "", "search_options": {}, "hits": []}
        )
        backend.create_note = AsyncMock(return_value=None)
        backend.metadata = AsyncMock(return_value=None)
        backend.toc = AsyncMock(return_value=[])
        backend.neighbors = AsyncMock(return_value=[])
        backend.related = AsyncMock(return_value=[])
        backend.stats = AsyncMock(return_value={"total_notes": 0})
        return backend

    def test_manager_initialization(self) -> None:
        backend = self._build_backend()
        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        assert manager.notebook_dir == Path("/tmp/test")
        assert manager.backend is backend

    def test_add_entity_creates_note_when_not_found(self) -> None:
        backend = self._build_backend()
        note = SimpleNamespace(filename_stem="python", created=None, modified=None)
        backend.create_note = AsyncMock(return_value=note)

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test", backend=backend)
        entity = manager.add_entity("Python", "SKILL", "Programming language")

        assert entity.note_id == "python"
        backend.create_note.assert_awaited_once()

    def test_add_entity_accepts_dict_writer_result(self) -> None:
        backend = self._build_backend()
        backend.create_note = AsyncMock(
            return_value={
                "id": "python",
                "created": "2026-02-18T00:00:00Z",
                "modified": "2026-02-18T00:00:00Z",
            }
        )

        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test", backend=backend)
        entity = manager.add_entity("Python", "SKILL", "Programming language")

        assert entity.note_id == "python"
        assert entity.created_at == "2026-02-18T00:00:00Z"

    def test_add_entity_uses_existing_hit(self) -> None:
        backend = self._build_backend()
        backend.search_planned = AsyncMock(
            return_value={
                "query": "Python",
                "search_options": {},
                "hits": [
                    SimpleNamespace(
                        stem="python",
                        title="Python",
                        path="docs/python.md",
                        score=1.0,
                    )
                ],
            }
        )
        manager = UnifiedKnowledgeManager(notebook_dir="/tmp/test", backend=backend)

        entity = manager.add_entity("Python", "SKILL", "Programming language")

        assert entity.note_id == "python"
        backend.create_note.assert_not_called()

    def test_search_uses_link_graph_backend(self) -> None:
        backend = self._build_backend()
        backend.search_planned = AsyncMock(
            return_value={
                "query": "python",
                "search_options": {},
                "hits": [
                    SimpleNamespace(
                        stem="python",
                        title="Python",
                        path="docs/python.md",
                        score=0.9,
                    )
                ],
            }
        )
        backend.metadata = AsyncMock(return_value=SimpleNamespace(tags=["skill"]))

        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        result = manager.search("python", limit=5)

        assert result["query"] == "python"
        assert result["parsed_query"] == "python"
        assert result["total"] == 1
        assert result["notes"][0]["title"] == "Python"
        assert result["notes"][0]["tags"] == ["skill"]
        backend.search_planned.assert_awaited_once()
        backend.metadata.assert_awaited_once()

    def test_get_stats_from_backend(self) -> None:
        backend = self._build_backend()
        backend.stats = AsyncMock(return_value={"total_notes": 20})
        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        stats = manager.get_stats()
        assert stats["total_notes"] == 20

    def test_list_by_tag_from_toc(self) -> None:
        backend = self._build_backend()
        backend.toc = AsyncMock(
            return_value=[
                {"id": "python", "title": "Python", "path": "python.md", "tags": ["skill"]},
                {"id": "rust", "title": "Rust", "path": "rust.md", "tags": ["lang"]},
            ]
        )
        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        rows = manager.list_by_tag("skill", limit=10)
        assert len(rows) == 1
        assert rows[0]["id"] == "python"

    def test_get_graph_builds_nodes_and_links(self) -> None:
        backend = self._build_backend()
        backend.toc = AsyncMock(
            return_value=[
                {"id": "python", "title": "Python", "path": "python.md", "tags": ["skill"]},
                {"id": "rust", "title": "Rust", "path": "rust.md", "tags": ["lang"]},
            ]
        )

        async def _neighbors(stem: str, **kwargs):
            del kwargs
            if stem == "python":
                return [SimpleNamespace(stem="rust")]
            return []

        backend.neighbors = AsyncMock(side_effect=_neighbors)
        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        graph = manager.get_graph(limit=10)

        assert len(graph["nodes"]) == 2
        assert {"source": "python", "target": "rust"} in graph["links"]

    def test_find_related_uses_backend(self) -> None:
        backend = self._build_backend()
        backend.related = AsyncMock(
            return_value=[SimpleNamespace(stem="rust", title="Rust", path="rust.md")]
        )
        manager = UnifiedKnowledgeManager(
            notebook_dir="/tmp/test",
            backend=backend,
        )
        out = manager.find_related("python", limit=5)
        assert out == [{"id": "rust", "title": "Rust", "path": "rust.md"}]

    def test_get_unified_manager_factory(self, monkeypatch) -> None:
        fake_backend = self._build_backend()

        monkeypatch.setattr(
            "omni.rag.unified_knowledge.get_link_graph_backend",
            lambda notebook_dir=None: fake_backend,
        )

        manager = get_unified_manager("/custom/path")
        assert isinstance(manager, UnifiedKnowledgeManager)
        assert manager.notebook_dir == Path("/custom/path")
        assert manager.backend is fake_backend
