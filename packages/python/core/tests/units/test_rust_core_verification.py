"""Rust Core Verification Tests

These tests validate that the Rust omni-vector core is functioning correctly.
Run with: uv run pytest packages/python/core/tests/units/test_rust_core_verification.py -v

This test module is automatically discovered by pytest and will run as part of
the standard test suite, ensuring Rust bindings are working after code changes.
"""

from __future__ import annotations

import pytest
import asyncio
import tempfile
from pathlib import Path


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


class TestRustVectorStore:
    """Tests for RustVectorStore creation and basic operations."""

    def test_in_memory_store_creation(self):
        """Test that in-memory RustVectorStore can be created."""
        from omni.foundation.bridge import RustVectorStore

        store = RustVectorStore(":memory:", dimension=1024, enable_keyword_index=False)
        assert store is not None

    def test_file_based_store_creation(self, project_root):
        """Test that file-based RustVectorStore can be created."""
        from omni.foundation.bridge import RustVectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = str(Path(tmpdir) / "test.lance")
            store = RustVectorStore(store_path, dimension=1024, enable_keyword_index=True)
            assert store is not None


class TestDatabasePaths:
    """Tests for database path functions."""

    def test_get_database_paths(self):
        """Test that get_database_paths returns all required paths."""
        from omni.agent.cli.commands.reindex import get_database_paths

        paths = get_database_paths()
        assert "skills" in paths, "Missing skills path"
        assert "router" in paths, "Missing router path"
        assert "knowledge" in paths, "Missing knowledge path"

    def test_paths_end_with_lance(self):
        """Test that database paths end with .lance extension."""
        from omni.agent.cli.commands.reindex import get_database_paths

        paths = get_database_paths()
        assert paths["skills"].endswith("skills.lance")
        assert paths["router"].endswith("router.lance")
        assert paths["knowledge"].endswith("knowledge.lance")


class TestReindexWorkflow:
    """Tests for the reindex all workflow."""

    def test_reindex_skills(self, project_root):
        """Test that skills can be reindexed."""
        from omni.agent.cli.commands.reindex import _reindex_skills

        result = _reindex_skills(clear=True)
        assert result["status"] == "success"
        assert result.get("tools_indexed", 0) > 0

    def test_sync_router_from_skills(self, project_root):
        """Test that router can be synced from skills."""
        from omni.agent.cli.commands.reindex import _sync_router_from_skills

        result = _sync_router_from_skills()
        assert result["status"] == "success"
        assert result.get("tools_indexed", 0) > 0

    def test_reindex_knowledge(self, project_root):
        """Test that knowledge base can be reindexed."""
        from omni.agent.cli.commands.reindex import _reindex_knowledge

        result = _reindex_knowledge(clear=True)
        assert result["status"] == "success"
        assert result.get("docs_indexed", 0) > 0


class TestKnowledgeBase:
    """Tests for knowledge base operations."""

    @pytest.fixture
    def librarian(self):
        """Create a test librarian instance."""
        from omni.core.knowledge.librarian import Librarian

        return Librarian(collection="test")

    def test_librarian_is_ready(self, librarian):
        """Test that librarian is ready after initialization."""
        assert librarian.is_ready

    def test_ingest_file(self, librarian, project_root):
        """Test that files can be ingested."""
        test_file = project_root / "scripts" / "verify-rust-core.py"
        if not test_file.exists():
            pytest.skip("Test file not found")

        success = librarian.ingest_file(str(test_file), {"type": "test"})
        assert success

    def test_commit_entries(self, librarian, project_root):
        """Test that entries can be committed."""
        test_file = project_root / "scripts" / "verify-rust-core.py"
        if not test_file.exists():
            pytest.skip("Test file not found")

        librarian.ingest_file(str(test_file), {"type": "test"})
        committed = asyncio.run(librarian.commit())
        assert committed >= 0

    @pytest.mark.asyncio
    async def test_search_knowledge(self, librarian):
        """Test that knowledge can be searched."""
        results = await librarian.search("test", limit=5)
        assert isinstance(results, list)


class TestRouterSearch:
    """Tests for router hybrid search."""

    @pytest.fixture
    def router(self):
        """Get router instance."""
        from omni.core.router.main import RouterRegistry

        return RouterRegistry.get()

    @pytest.mark.asyncio
    async def test_route_hybrid_finds_results(self, router):
        """Test that route_hybrid finds results for valid queries."""
        results = await router.route_hybrid("find python files", limit=5, threshold=0.1)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_route_hybrid_result_structure(self, router):
        """Test that route_hybrid returns properly structured results."""
        results = await router.route_hybrid("find files", limit=5, threshold=0.1)

        if results:
            first = results[0]
            assert hasattr(first, "skill_name")
            assert hasattr(first, "command_name")
            assert hasattr(first, "score")
            assert hasattr(first, "confidence")

    @pytest.mark.asyncio
    async def test_route_hybrid_confidence_levels(self, router):
        """Test that confidence levels are correctly assigned."""
        results = await router.route_hybrid("git commit", limit=10, threshold=0.0)

        for r in results:
            assert r.confidence.value in ("high", "medium", "low")


class TestSkillDiscoverPattern:
    """Tests for skill.discover pattern using route_hybrid."""

    @pytest.fixture
    def router(self):
        """Get router instance."""
        from omni.core.router.main import RouterRegistry

        return RouterRegistry.get()

    @pytest.mark.asyncio
    async def test_discover_finds_smart_find_tool(self, router):
        """Test that smart_find tool is discoverable."""
        results = await router.route_hybrid(
            "find python files in directory", limit=10, threshold=0.1
        )

        tool_names = [f"{r.skill_name}.{r.command_name}" for r in results]
        assert any("smart_find" in name for name in tool_names), (
            f"Expected smart_find in results, got: {tool_names}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
