"""Tests for omni.core.router.indexer module.

Tests the optimized batch indexing functionality and singleton patterns.
"""

from __future__ import annotations

import asyncio
import pytest

from omni.core.router.indexer import IndexedEntry, InMemoryIndex, IndexedSkill, SkillIndexer
from omni.foundation.config.settings import get_setting


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
        """Test default initialization uses unified path."""
        expected_dimension = get_setting("embedding.dimension", 1024)
        indexer = SkillIndexer()

        # Default should use unified path
        assert "omni-vector" in indexer._storage_path
        assert "router.lance" in indexer._storage_path
        assert indexer._dimension == expected_dimension
        assert indexer._store is None
        assert indexer._indexed_count == 0

    def test_in_memory_initialization(self):
        """Test in-memory mode initialization."""
        expected_dimension = get_setting("embedding.dimension", 1024)
        indexer = SkillIndexer(storage_path=":memory:")

        assert indexer._storage_path == ":memory:"
        assert indexer._dimension == expected_dimension
        assert indexer._store is None
        assert indexer._indexed_count == 0

    def test_custom_initialization(self):
        """Test custom initialization."""
        indexer = SkillIndexer(storage_path="/test/path", dimension=768)

        assert indexer._storage_path == "/test/path"
        assert indexer._dimension == 768

    def test_is_ready_false_when_not_initialized(self):
        """Test is_ready returns False before initialization."""
        indexer = SkillIndexer(storage_path=":memory:")

        assert indexer.is_ready is False

    def test_get_stats(self):
        """Test get_stats returns correct info."""
        indexer = SkillIndexer()

        # get_stats is async, run it with asyncio.run
        stats = asyncio.run(indexer.get_stats())

        assert "entries_indexed" in stats
        assert "is_ready" in stats
        assert "storage_path" in stats
        assert stats["entries_indexed"] == 0
        assert stats["is_ready"] is False
        # Default uses unified path
        assert "omni-vector" in stats["storage_path"]


class TestInMemoryIndex:
    """Test InMemoryIndex class (fallback when RustVectorStore unavailable)."""

    def test_initialization(self):
        """Test InMemoryIndex initialization."""
        index = InMemoryIndex(dimension=384)

        assert index._dimension == 384
        assert len(index._entries) == 0

    def test_add_single_entry(self):
        """Test adding a single entry."""
        index = InMemoryIndex()
        index.add("test content", {"type": "skill", "skill_name": "test"})

        assert len(index._entries) == 1
        entry = index._entries[0]
        assert entry.content == "test content"
        assert entry.metadata["type"] == "skill"

    def test_add_batch(self):
        """Test adding entries in batch."""
        index = InMemoryIndex()

        entries = [
            ("content 1", {"id": "1"}),
            ("content 2", {"id": "2"}),
            ("content 3", {"id": "3"}),
        ]
        index.add_batch(entries)

        assert len(index._entries) == 3
        assert index._entries[0].content == "content 1"
        assert index._entries[1].content == "content 2"
        assert index._entries[2].content == "content 3"

    def test_clear(self):
        """Test clearing the index."""
        index = InMemoryIndex()
        index.add("content 1", {"id": "1"})
        index.add("content 2", {"id": "2"})

        assert len(index._entries) == 2

        index.clear()

        assert len(index._entries) == 0

    def test_search_empty(self):
        """Test search on empty index."""
        index = InMemoryIndex()

        results = index.search("test", None, limit=5)

        assert results == []

    def test_search_with_keyword_match(self):
        """Test keyword-based search (fallback when embeddings unavailable)."""
        index = InMemoryIndex()
        index.add("Git commit changes", {"skill_name": "git"})
        index.add("File system read", {"skill_name": "filesystem"})
        index.add("Memory save", {"skill_name": "memory"})

        results = index.search("git commit", None, limit=5)

        assert len(results) >= 1
        # First result should be git-related
        assert results[0].payload["skill_name"] == "git"

    def test_len(self):
        """Test __len__ method."""
        index = InMemoryIndex()
        assert len(index) == 0

        index.add("content", {})
        assert len(index) == 1

        index.add_batch([("a", {}), ("b", {})])
        assert len(index) == 3


class TestIndexedEntry:
    """Test IndexedEntry dataclass."""

    def test_create_indexed_entry(self):
        """Test creating an IndexedEntry."""
        entry = IndexedEntry(
            content="Test content",
            metadata={"skill_name": "test", "weight": 1.0},
            embedding=[0.1, 0.2, 0.3],
        )

        assert entry.content == "Test content"
        assert entry.metadata["skill_name"] == "test"
        assert entry.embedding == [0.1, 0.2, 0.3]

    def test_indexed_entry_without_embedding(self):
        """Test creating an IndexedEntry without embedding."""
        entry = IndexedEntry(content="No embedding", metadata={})

        assert entry.content == "No embedding"
        assert entry.embedding is None


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
        indexer = SkillIndexer(storage_path=":memory:")
        count = await indexer.index_skills([])

        assert count == 0

    @pytest.mark.asyncio
    async def test_index_skills_in_memory_mode(self):
        """Test in-memory indexing (no RustVectorStore required)."""
        indexer = SkillIndexer(storage_path=":memory:")

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

        # Should have 1 skill entry + 2 command entries = 3 total
        assert count == 3

    @pytest.mark.asyncio
    async def test_index_skills_in_memory_clear_and_reindex(self):
        """Test that in-memory index clears before re-indexing."""
        indexer = SkillIndexer(storage_path=":memory:")

        skills1 = [
            {"name": "git", "description": "Git skill", "commands": []},
        ]
        await indexer.index_skills(skills1)
        assert indexer._indexed_count == 1

        # Re-index with different skills
        skills2 = [
            {"name": "memory", "description": "Memory skill", "commands": []},
            {"name": "filesystem", "description": "FS skill", "commands": []},
        ]
        await indexer.index_skills(skills2)
        # Should replace, not append
        assert indexer._indexed_count == 2

    @pytest.mark.asyncio
    async def test_index_skills_multiple_skills_batch(self):
        """Test batch indexing of multiple skills."""
        indexer = SkillIndexer(storage_path=":memory:")

        skills = [
            {
                "name": "git",
                "description": "Git operations",
                "commands": [
                    {"name": "status", "description": "Show status"},
                    {"name": "commit", "description": "Commit"},
                    {"name": "push", "description": "Push changes"},
                ],
            },
            {
                "name": "memory",
                "description": "Memory storage",
                "commands": [
                    {"name": "save", "description": "Save memory"},
                ],
            },
        ]

        count = await indexer.index_skills(skills)

        # 1 skill entry + 3 git commands + 1 memory skill + 1 memory command = 6
        assert count == 6

    @pytest.mark.asyncio
    async def test_index_skills_skills_without_commands(self):
        """Test indexing skills without commands."""
        indexer = SkillIndexer(storage_path=":memory:")

        skills = [
            {"name": "solo", "description": "Solo skill", "commands": []},
        ]

        count = await indexer.index_skills(skills)

        assert count == 1

    @pytest.mark.asyncio
    @indexing_available
    async def test_index_skills_single_skill(self):
        """Test indexing a single skill."""
        # Use in-memory storage for test isolation
        indexer = SkillIndexer(storage_path=":memory:")

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
        # Use in-memory storage for test isolation
        indexer = SkillIndexer(storage_path=":memory:")

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

        stats = await indexer.get_stats()
        assert stats["entries_indexed"] >= 1


class TestSkillIndexerSearch:
    """Test skill index search functionality."""

    @pytest.mark.asyncio
    @indexing_available
    async def test_search_empty_index(self):
        """Test searching empty index returns empty list."""
        indexer = SkillIndexer(storage_path=":memory:")

        results = await indexer.search("test query")

        assert results == []

    @pytest.mark.asyncio
    @indexing_available
    async def test_search_with_limit(self):
        """Test search respects limit parameter."""
        indexer = SkillIndexer(storage_path=":memory:")

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
        indexer = SkillIndexer(storage_path=":memory:")

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
