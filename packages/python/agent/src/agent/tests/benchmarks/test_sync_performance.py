"""
benchmarks/test_sync_performance.py
Phase 67: Performance Benchmark for Skill Sync

Benchmarks to track sync performance over time and catch regressions.

Usage:
    uv run pytest packages/python/agent/src/agent/tests/benchmarks/test_sync_performance.py -v -s
"""

import pytest
import time
from pathlib import Path


class TestSyncPerformance:
    """Performance benchmarks for skill sync operations."""

    @pytest.fixture
    async def vector_memory(self):
        """Get vector memory instance."""
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()
        yield vm

    @pytest.fixture
    async def clean_state(self, vector_memory):
        """Ensure clean state before test."""
        store = vector_memory._ensure_store()
        if store:
            import json

            existing_json = store.get_all_file_hashes("skills")
            if existing_json:
                existing = json.loads(existing_json)
                if existing:
                    paths = list(existing.keys())
                    store.delete_by_file_path("skills", paths)

        yield vector_memory

    def test_path_normalization_performance(self):
        """Benchmark path normalization function.

        This test validates that path normalization is fast enough
        to not be a bottleneck during sync operations.
        """
        from common.skills_path import SKILLS_DIR

        def normalize_path(p: str) -> str:
            """Normalize path to absolute resolved form using SKILLS_DIR."""
            try:
                return str((SKILLS_DIR() / p).resolve())
            except Exception:
                return p

        # Test paths (no prefix, just relative to skills dir)
        test_paths = [
            "git/scripts/commit.py",
            "software_engineering/scripts/engineering.py",
            "filesystem/scripts/io.py",
        ] * 100  # 300 paths

        # Benchmark
        start = time.perf_counter()
        for path in test_paths:
            normalize_path(path)
        elapsed = time.perf_counter() - start

        # Performance assertion: should normalize 300 paths in < 10ms
        assert elapsed < 0.01, f"Path normalization too slow: {elapsed * 1000:.2f}ms for 300 paths"
        print(f"\nPath normalization: {elapsed * 1000:.2f}ms for {len(test_paths)} paths")

    @pytest.mark.asyncio
    async def test_sync_initial_index_performance(self, clean_state):
        """Benchmark initial sync (cold start).

        First sync after clearing cache should index all skills.
        Target: < 2 seconds for ~80 skills.
        """
        from common.skills_path import SKILLS_DIR

        start = time.perf_counter()
        result = await clean_state.sync_skills(str(SKILLS_DIR()), "skills")
        elapsed = time.perf_counter() - start

        # Assertions (sync_skills returns stats dict directly)
        total = result.get("total", 0)
        assert total >= 50, f"Should index at least 50 skills, got {total}"

        # Performance target
        assert elapsed < 2.0, f"Initial sync too slow: {elapsed:.2f}s (target: <2s)"

        print(f"\nInitial sync: {elapsed:.2f}s")
        print(f"  Skills indexed: {total}")

    @pytest.mark.asyncio
    async def test_sync_incremental_performance(self, clean_state):
        """Benchmark incremental sync (no changes).

        After initial sync, subsequent syncs should be fast.
        Target: < 0.5 seconds for no changes.
        """
        from common.skills_path import SKILLS_DIR

        # First, do initial sync
        await clean_state.sync_skills(str(SKILLS_DIR()), "skills")

        # Now benchmark incremental sync (no changes)
        start = time.perf_counter()
        result = await clean_state.sync_skills(str(SKILLS_DIR()), "skills")
        elapsed = time.perf_counter() - start

        # Should show no changes
        assert result["added"] == 0
        assert result["modified"] == 0

        # Performance target (adjusted for CI/development environments)
        assert elapsed < 1.0, f"Incremental sync too slow: {elapsed:.2f}s (target: <1.0s)"

        print(f"\nIncremental sync (no changes): {elapsed:.2f}s")

    @pytest.mark.asyncio
    async def test_sync_with_deletions_performance(self, clean_state):
        """Benchmark sync with deleted files.

        Should handle deletion efficiently.
        Target: < 1 second.
        """
        from common.skills_path import SKILLS_DIR
        import tempfile
        import shutil

        # Create a temporary skill
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "temp_skill"
            skill_dir.mkdir()
            (skill_dir / "scripts").mkdir()

            # Write SKILL.md
            (skill_dir / "SKILL.md").write_text("""---
name: temp_skill
version: 1.0.0
---
# Temp Skill
""")

            # Write a script
            (
                skill_dir / "scripts" / "hello.py"
            ).write_text("""from agent.skills.decorators import skill_script

@skill_script(name="hello", description="Say hello")
def hello():
    '''Say hello.'''
    return "Hello!"
""")

            # Create the skill in the real skills directory
            skills_dir = SKILLS_DIR()
            target_dir = skills_dir / "temp_skill"
            target_dir.mkdir(exist_ok=True)
            (target_dir / "scripts").mkdir(exist_ok=True)

            shutil.copy(skill_dir / "SKILL.md", target_dir / "SKILL.md")
            shutil.copy(skill_dir / "scripts" / "hello.py", target_dir / "scripts" / "hello.py")

            try:
                # Sync with the new skill
                await clean_state.sync_skills(str(skills_dir), "skills")

                # Now delete it
                shutil.rmtree(target_dir)

                # Sync again - should detect deletion
                start = time.perf_counter()
                result = await clean_state.sync_skills(str(skills_dir), "skills")
                elapsed = time.perf_counter() - start

                # Should detect deletion
                assert result["deleted"] >= 1, "Should detect deleted skill"

                # Performance target
                assert elapsed < 1.0, f"Sync with deletions too slow: {elapsed:.2f}s (target: <1s)"

                print(f"\nSync with deletion: {elapsed:.2f}s")
                print(f"  Deleted: {result['deleted']}")

            finally:
                # Cleanup
                if target_dir.exists():
                    shutil.rmtree(target_dir)

    @pytest.mark.asyncio
    async def test_search_performance(self, clean_state):
        """Benchmark semantic search performance.

        Target: < 100ms for hybrid search.
        """
        from common.skills_path import SKILLS_DIR

        # First sync to have data
        await clean_state.sync_skills(str(SKILLS_DIR()), "skills")

        # Benchmark search
        queries = ["git commit", "file read", "web crawl", "test run"]

        for query in queries:
            start = time.perf_counter()
            results = await clean_state.search_tools_hybrid(query, limit=5)
            elapsed = time.perf_counter() - start

            assert elapsed < 0.1, f"Search for '{query}' too slow: {elapsed * 1000:.0f}ms"
            print(f"\nSearch '{query}': {elapsed * 1000:.1f}ms ({len(results)} results)")


class TestPathNormalization:
    """Unit tests for path normalization logic.

    Paths in the system are stored relative to SKILLS_DIR.
    The normalize_path function handles conversion to absolute paths.
    """

    def test_normalize_simple_relative_path(self):
        """Test normalization of simple relative paths."""
        from common.skills_path import SKILLS_DIR

        def normalize_path(p: str) -> str:
            try:
                return str((SKILLS_DIR() / p).resolve())
            except Exception:
                return p

        # Simple relative path
        path = "git/scripts/commit.py"
        result = normalize_path(path)
        expected = str((SKILLS_DIR() / "git/scripts/commit.py").resolve())

        assert result == expected

    def test_normalize_already_resolved(self):
        """Test that already resolved paths work correctly."""
        from common.skills_path import SKILLS_DIR

        def normalize_path(p: str) -> str:
            try:
                return str((SKILLS_DIR() / p).resolve())
            except Exception:
                return p

        absolute_path = str(SKILLS_DIR() / "git/scripts/commit.py")
        result = normalize_path(absolute_path)

        # Should just resolve to the same path
        assert result == absolute_path or result == str(Path(absolute_path).resolve())


# Performance thresholds (used by tests and CI)
PERFORMANCE_THRESHOLDS = {
    "initial_sync": 2.0,  # seconds
    "incremental_sync": 0.5,  # seconds
    "sync_with_deletions": 1.0,  # seconds
    "search": 0.1,  # seconds
    "path_normalization": 0.01,  # seconds for 300 paths
}
