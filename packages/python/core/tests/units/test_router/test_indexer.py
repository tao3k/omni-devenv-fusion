"""Tests for omni.core.router.indexer module.

Tests the optimized batch indexing functionality and singleton patterns.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from omni.test_kit.fixtures.vector import make_tool_search_payload

from omni.core.router.indexer import IndexedSkill, SkillIndexer
from omni.foundation.config.settings import get_setting


def _is_indexing_available() -> bool:
    """Check if skill indexing is fully available (RustVectorStore + embedding service)."""
    try:
        from omni.foundation.bridge import RustVectorStore

        # Verify RustVectorStore can be created
        _ = RustVectorStore(":memory:", 1536)

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
        """Test in-memory mode initialization (Rust in-memory backend)."""
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
    async def test_index_skills_normalizes_prefixed_command_name(self):
        """When command name already includes skill prefix, avoid double prefix in IDs."""
        indexer = SkillIndexer(storage_path=":memory:")
        fake_memory = MagicMock()
        indexer._memory_index = fake_memory

        skills = [
            {
                "name": "advanced_tools",
                "description": "Advanced tools",
                "commands": [
                    {
                        "name": "advanced_tools.smart_find",
                        "description": "Find files",
                    }
                ],
            }
        ]

        count = await indexer.index_skills(skills)
        assert count == 2
        fake_memory.add_batch.assert_called_once()

        entries = fake_memory.add_batch.call_args.args[0]
        command_entry = next(
            metadata for _, metadata in entries if metadata.get("type") == "command"
        )
        assert command_entry["tool_name"] == "advanced_tools.smart_find"
        assert command_entry["id"] == "advanced_tools.smart_find"

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

    @pytest.mark.asyncio
    async def test_search_rust_path_uses_search_tools(self):
        """Rust-backed search should use explicit search_tools path."""
        indexer = SkillIndexer(storage_path=":memory:")
        indexer._store = MagicMock()
        indexer._embedding_service = MagicMock()
        indexer._embedding_service.embed.return_value = [[0.1, 0.2, 0.3]]
        indexer._store.search_tools = AsyncMock(
            return_value=[
                make_tool_search_payload(
                    name="git.status",
                    tool_name="git.status",
                    description="Show status",
                    input_schema={},
                    file_path="skills/git.py",
                    score=0.8,
                    vector_score=0.7,
                    keyword_score=0.6,
                    final_score=0.82,
                    confidence="high",
                    routing_keywords=["git", "status"],
                )
            ]
        )

        results = await indexer.search("git status", limit=3, threshold=0.1)

        assert len(results) == 1
        assert results[0].id == "git.status"
        assert results[0].score == 0.8
        assert results[0].payload["skill_name"] == "git"
        indexer._store.search_tools.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_rust_path_applies_threshold(self):
        """Rust-backed search should filter low-scoring records."""
        indexer = SkillIndexer(storage_path=":memory:")
        indexer._store = MagicMock()
        indexer._embedding_service = MagicMock()
        indexer._embedding_service.embed.return_value = [[0.1, 0.2, 0.3]]
        indexer._store.search_tools = AsyncMock(
            return_value=[
                make_tool_search_payload(
                    name="git.status",
                    tool_name="git.status",
                    description="Show status",
                    input_schema={},
                    file_path="skills/git.py",
                    score=0.2,
                    vector_score=0.2,
                    keyword_score=0.2,
                    final_score=0.2,
                    confidence="low",
                    routing_keywords=["git", "status"],
                ),
                make_tool_search_payload(
                    name="git.commit",
                    tool_name="git.commit",
                    description="Commit changes",
                    input_schema={},
                    file_path="skills/git.py",
                    score=0.95,
                    vector_score=0.9,
                    keyword_score=0.85,
                    final_score=0.96,
                    confidence="high",
                    routing_keywords=["git", "commit"],
                ),
            ]
        )

        results = await indexer.search("git", limit=5, threshold=0.9)

        assert len(results) == 1
        assert results[0].id == "git.commit"
        assert results[0].score >= 0.9
