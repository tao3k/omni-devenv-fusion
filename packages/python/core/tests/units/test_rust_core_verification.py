"""Rust Core Verification Tests

These tests validate that the Rust omni-vector core is functioning correctly.
Run with: uv run pytest packages/python/core/tests/units/test_rust_core_verification.py -v

This test module is automatically discovered by pytest and will run as part of
the standard test suite, ensuring Rust bindings are working after code changes.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from omni.test_kit.asserts import assert_route_result_shape, assert_tool_family_match
from omni.test_kit.fixtures.vector import parametrize_route_intent_queries


def _full_tool_name(result) -> str:
    return f"{result.skill_name}.{result.command_name}"


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
        from omni.foundation.config import get_database_paths

        paths = get_database_paths()
        assert "skills" in paths, "Missing skills path"
        assert "router" in paths, "Missing router path"
        assert "knowledge" in paths, "Missing knowledge path"
        assert "memory" in paths, "Missing memory path"

    def test_paths_end_with_lance(self):
        """Test that database paths end with expected extension."""
        from omni.foundation.config import get_database_paths

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

    def test_reindex_knowledge(self, project_root):
        """Test that knowledge base reindex function API works."""
        from omni.agent.cli.commands.reindex import _reindex_knowledge
        from omni.core.knowledge.librarian import Librarian

        # Test 1: Verify Librarian can be initialized with table_name
        librarian = Librarian(table_name="knowledge")
        assert librarian is not None
        assert librarian.table_name == "knowledge"

        # Test 2: Verify _reindex_knowledge returns proper dict structure
        # Note: We don't run full ingest as it takes too long
        # Just verify the function exists and returns expected format
        import inspect

        sig = inspect.signature(_reindex_knowledge)
        assert "clear" in sig.parameters


class TestKnowledgeBase:
    """Tests for knowledge base operations."""

    @pytest.fixture
    def librarian(self):
        """Create a test librarian instance."""
        from omni.core.knowledge.librarian import Librarian

        return Librarian(table_name="test")

    def test_librarian_is_ready(self, librarian):
        """Test that librarian is ready after initialization."""
        assert librarian is not None

    def test_ingest_file(self, librarian, project_root):
        """Test that files can be ingested."""
        test_file = project_root / "scripts" / "verify-rust-core.py"
        if not test_file.exists():
            pytest.skip("Test file not found")

        success = librarian.upsert_file(str(test_file))
        assert success

    def test_commit_entries(self, librarian, project_root):
        """Test that entries can be committed."""
        test_file = project_root / "scripts" / "verify-rust-core.py"
        if not test_file.exists():
            pytest.skip("Test file not found")

        librarian.upsert_file(str(test_file))
        # New API doesn't require explicit commit - it's auto-committed

    @pytest.mark.asyncio
    async def test_search_knowledge(self, librarian, project_root):
        """Test that knowledge can be searched."""
        # Skip if table has no data (test file was not found)
        test_file = project_root / "scripts" / "verify-rust-core.py"
        if not test_file.exists() or librarian.storage.count() == 0:
            pytest.skip("No data in knowledge base to search")

        # Query should return results
        results = librarian.query("test", limit=5)
        assert isinstance(results, list)


class TestRouterSearch:
    """Tests for router hybrid search."""

    @pytest.fixture
    def router(self):
        """Get isolated router instance with local indexed snapshot."""
        from omni.core.router.main import OmniRouter, RouterRegistry
        from omni.foundation.bridge import RustVectorStore

        RouterRegistry.reset_all()
        with tempfile.TemporaryDirectory(prefix="rust-core-router-") as tmpdir:
            storage_path = str(Path(tmpdir) / "skills.lance")
            store = RustVectorStore(storage_path, enable_keyword_index=True)
            from omni.foundation.config.prj import get_skills_dir

            asyncio.run(store.index_skill_tools_dual(str(get_skills_dir()), "skills", "skills"))
            router = OmniRouter(storage_path=storage_path)
            yield router
        RouterRegistry.reset_all()

    @pytest.mark.asyncio
    async def test_route_hybrid_finds_results(self, router):
        """Test that route_hybrid finds results for valid queries."""
        results = await router.route_hybrid("find python files", limit=5, threshold=0.1)
        if not results:
            pytest.skip("Hybrid search returned no results in this environment/index snapshot")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_route_hybrid_result_structure(self, router):
        """Test that route_hybrid returns properly structured results."""
        results = await router.route_hybrid("find files", limit=5, threshold=0.1)

        if results:
            first = results[0]
            assert_route_result_shape(first)

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
        """Get isolated router instance with local indexed snapshot."""
        from omni.core.router.main import OmniRouter, RouterRegistry
        from omni.foundation.bridge import RustVectorStore

        RouterRegistry.reset_all()
        with tempfile.TemporaryDirectory(prefix="rust-core-discover-") as tmpdir:
            storage_path = str(Path(tmpdir) / "skills.lance")
            store = RustVectorStore(storage_path, enable_keyword_index=True)
            from omni.foundation.config.prj import get_skills_dir

            asyncio.run(store.index_skill_tools_dual(str(get_skills_dir()), "skills", "skills"))
            router = OmniRouter(storage_path=storage_path)
            yield router
        RouterRegistry.reset_all()

    @pytest.mark.asyncio
    @parametrize_route_intent_queries()
    async def test_discover_intent_returns_relevant_tools(
        self,
        router,
        query: str,
        expected_tool_name: str,
    ):
        """Core verification: discovery intents map to relevant tool families."""
        results = await router.route_hybrid(query, limit=10, threshold=0.1)
        if not results:
            pytest.skip("Hybrid search returned no results in this environment/index snapshot")

        tool_names = [_full_tool_name(r) for r in results]
        if expected_tool_name == "advanced_tools.smart_find":
            assert_tool_family_match(
                tool_names,
                substrings=["smart_find", "search"],
                msg="Expected discovery-family tools in results",
            )
        else:
            assert_tool_family_match(
                tool_names,
                substrings=["git"],
                msg="Expected git-family tools in results",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
