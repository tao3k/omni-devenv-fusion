"""Tests for omni.core.router.indexer module."""

from __future__ import annotations

import pytest
from omni.core.router.indexer import SkillIndexer, IndexedSkill


def _is_indexing_available() -> bool:
    """Check if skill indexing is fully available (RustVectorStore + embedding service)."""
    try:
        from omni.foundation.bridge import RustVectorStore

        # Verify RustVectorStore can be created
        store = RustVectorStore(":memory:", 1536)

        # Verify embedding service can be imported and used
        from omni.foundation.services.embedding import get_embedding_service

        service = get_embedding_service()
        # Quick test - just verify the service can be accessed
        _ = service.embed("test")

        return True
    except Exception:
        return False


# Marker for tests requiring full indexing capabilities
indexing_available = pytest.mark.skipif(
    not _is_indexing_available(),
    reason="Skill indexing unavailable (Rust bridge or embedding service not configured)",
)


class TestSkillIndexer:
    """Test SkillIndexer class."""

    def test_default_initialization(self):
        """Test default initialization."""
        indexer = SkillIndexer()

        assert indexer._storage_path == ":memory:"
        assert indexer._dimension == 1536
        assert indexer._store is None
        assert indexer._indexed_count == 0

    def test_custom_initialization(self):
        """Test custom initialization."""
        indexer = SkillIndexer(storage_path="/test/path", dimension=768)

        assert indexer._storage_path == "/test/path"
        assert indexer._dimension == 768

    def test_is_ready_false_when_not_initialized(self):
        """Test is_ready returns False before initialization."""
        indexer = SkillIndexer()

        assert indexer.is_ready is False

    def test_get_stats(self):
        """Test get_stats returns correct info."""
        indexer = SkillIndexer()

        stats = indexer.get_stats()

        assert "entries_indexed" in stats
        assert "is_ready" in stats
        assert "storage_path" in stats
        assert stats["entries_indexed"] == 0
        assert stats["is_ready"] is False
        assert stats["storage_path"] == ":memory:"


class TestIndexedSkill:
    """Test IndexedSkill dataclass."""

    def test_create_indexed_skill(self):
        """Test creating an IndexedSkill."""
        skill = IndexedSkill(
            skill_name="git",
            command_name="commit",
            content="Command commit: Commit changes",
            metadata={"weight": 2.0},
        )

        assert skill.skill_name == "git"
        assert skill.command_name == "commit"
        assert "commit" in skill.content
        assert skill.metadata["weight"] == 2.0

    def test_indexed_skill_without_command(self):
        """Test IndexedSkill for skill-level entry."""
        skill = IndexedSkill(
            skill_name="git",
            command_name=None,
            content="Skill git: Git operations",
            metadata={"type": "skill"},
        )

        assert skill.skill_name == "git"
        assert skill.command_name is None
        assert "Git operations" in skill.content


class TestSkillIndexerIndexing:
    """Test skill indexing functionality."""

    @pytest.mark.asyncio
    async def test_index_skills_empty_list(self):
        """Test indexing with empty skill list."""
        indexer = SkillIndexer()
        count = await indexer.index_skills([])

        assert count == 0

    @pytest.mark.asyncio
    @indexing_available
    async def test_index_skills_single_skill(self):
        """Test indexing a single skill."""
        indexer = SkillIndexer()

        skills = [
            {
                "name": "git",
                "description": "Git operations skill",
                "commands": [
                    {"name": "status", "description": "Show working tree status"},
                    {"name": "commit", "description": "Commit changes"},
                ],
            }
        ]

        count = await indexer.index_skills(skills)

        # Should have skill entry + 2 command entries
        assert count >= 1  # At least the skill entry

    @pytest.mark.asyncio
    @indexing_available
    async def test_index_skills_extracts_metadata(self):
        """Test that indexing extracts correct metadata."""
        indexer = SkillIndexer()

        skills = [
            {
                "name": "memory",
                "description": "Memory storage skill",
                "commands": [
                    {"name": "save", "description": "Save to memory"},
                ],
            }
        ]

        await indexer.index_skills(skills)

        stats = indexer.get_stats()
        assert stats["entries_indexed"] >= 1


class TestSkillIndexerSearch:
    """Test skill index search functionality."""

    @pytest.mark.asyncio
    @indexing_available
    async def test_search_empty_index(self):
        """Test searching empty index returns empty list."""
        indexer = SkillIndexer()

        results = await indexer.search("test query")

        assert results == []

    @pytest.mark.asyncio
    @indexing_available
    async def test_search_with_limit(self):
        """Test search respects limit parameter."""
        indexer = SkillIndexer()

        # Index some data first
        skills = [
            {
                "name": "test",
                "description": "Test skill",
                "commands": [{"name": "cmd1", "description": "Command 1"}],
            }
        ]
        await indexer.index_skills(skills)

        results = await indexer.search("test", limit=1)

        assert len(results) <= 1

    @pytest.mark.asyncio
    @indexing_available
    async def test_search_with_threshold(self):
        """Test search with threshold filtering."""
        indexer = SkillIndexer()

        # Index some data
        skills = [
            {
                "name": "test",
                "description": "Test skill",
                "commands": [{"name": "cmd1", "description": "Command 1"}],
            }
        ]
        await indexer.index_skills(skills)

        # Search with high threshold
        results = await indexer.search("test", threshold=0.99)

        # Results may be empty if no high-confidence matches
        for r in results:
            assert r.score >= 0.99
