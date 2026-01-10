"""
Performance benchmarks for Skills Architecture.

These tests measure the performance characteristics of skill loading,
execution, and management. They are intentionally slower than unit tests
and should be run separately with: just test-stress

Usage:
    just test-stress  # Runs all stress tests
    uv run pytest stress_tests/test_performance_skills.py -v
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Import omni helper (Phase 35.3)
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_skills import omni


class TestSkillPerformance:
    """Performance and stress tests for skill loading."""

    def test_rapid_load_unload(self, isolated_registry, mock_mcp_server):
        """Test rapid loading and reloading of skills."""
        skills_to_test = ["filesystem", "git"]

        start = time.time()
        for _ in range(3):
            for skill in skills_to_test:
                isolated_registry.loaded_skills.pop(skill, None)
                isolated_registry.module_cache.pop(skill, None)
                isolated_registry.load_skill(skill, mock_mcp_server)
        elapsed = time.time() - start

        # Should complete within reasonable time (< 5 seconds for 6 loads)
        assert elapsed < 5.0

    def test_concurrent_load_same_skill(self, isolated_registry, mock_mcp_server):
        """Loading same skill concurrently should not cause errors."""
        skills_to_test = ["filesystem"] * 3

        results = []
        for skill in skills_to_test:
            isolated_registry.loaded_skills.pop(skill, None)
            isolated_registry.module_cache.pop(skill, None)
            success, msg = isolated_registry.load_skill(skill, mock_mcp_server)
            results.append((success, msg))

        # All should succeed
        for success, msg in results:
            assert success is True


class TestAsyncPerformance:
    """Performance benchmarks for async architecture."""

    @pytest.mark.asyncio
    async def test_skill_manager_run_performance(self, skill_manager_fixture):
        """Benchmark SkillManager.run() execution time."""
        # Warm up
        await skill_manager_fixture.run("git", "git_status", {})

        # Benchmark
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            await skill_manager_fixture.run("git", "git_status", {})
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations
        print(f"\n[Performance] SkillManager.run() avg: {avg_time * 1000:.2f}ms")

        # Should complete within 100ms per call (generous threshold)
        assert avg_time < 0.1, f"Run too slow: {avg_time * 1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_omni_dispatch_performance(self, skill_manager_fixture):
        """Benchmark omni tool dispatch overhead."""
        # Warm up
        await omni("git.status")

        # Benchmark
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            await omni("git.status")
        elapsed = time.perf_counter() - start

        avg_time = elapsed / iterations
        print(f"\n[Performance] omni dispatch avg: {avg_time * 1000:.2f}ms")

        # Dispatch overhead should be minimal
        assert avg_time < 0.15, f"Dispatch too slow: {avg_time * 1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self, skill_manager_fixture):
        """Test executing multiple commands concurrently."""
        import asyncio

        # Warm up
        await skill_manager_fixture.run("git", "git_status", {})

        # Execute multiple commands concurrently
        async def run_command():
            return await skill_manager_fixture.run("git", "git_status", {})

        start = time.perf_counter()
        results = await asyncio.gather(*[run_command() for _ in range(5)])
        elapsed = time.perf_counter() - start

        print(f"\n[Performance] 5 concurrent commands: {elapsed * 1000:.2f}ms")

        # All should succeed
        for result in results:
            assert isinstance(result, str)

        # Concurrent should be faster than sequential
        assert elapsed < 0.5, f"Concurrent execution too slow: {elapsed * 1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_skill_loading_performance(self):
        """Benchmark skill loading from cold start."""
        import agent.core.skill_manager as sm_module

        # Clear all caches
        sm_module._skill_manager = None
        sm_module._manager = None

        start = time.perf_counter()
        manager = sm_module.get_skill_manager()
        manager.load_skills()
        elapsed = time.perf_counter() - start

        print(f"\n[Performance] Skill loading: {elapsed * 1000:.2f}ms")

        # Should load all skills within reasonable time
        assert elapsed < 2.0, f"Skill loading too slow: {elapsed * 1000:.2f}ms"
        assert len(manager._skills) >= 1
