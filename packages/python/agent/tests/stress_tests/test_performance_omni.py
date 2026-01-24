"""
Performance benchmarks for Omni One Tool Architecture - Trinity Architecture v2.0

These tests measure the dispatch latency and throughput of the
single 'omni' tool. They are intentionally slower than unit tests
and should be run separately.

Usage:
    just test-stress
    uv run pytest packages/python/agent/tests/stress_tests/test_performance_omni.py -v
"""

import time
from pathlib import Path

import pytest


class TestOmniPerformance:
    """Performance benchmarks for Trinity Architecture dispatch."""

    @pytest.mark.asyncio
    async def test_git_skill_dispatch_latency(self, git_skill):
        """Measure git skill command dispatch latency."""
        iterations = 5
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await git_skill.execute("status")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print("\n[Performance] Git Status Dispatch Latency:")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   Min: {min(latencies):.1f}ms")
        print(f"   Max: {max(latencies):.1f}ms")

        # Should be under 100ms for local commands
        assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms exceeds 100ms threshold"

    @pytest.mark.asyncio
    async def test_skill_reload_performance(self, skills_root: Path):
        """Measure skill loading/reloading performance."""
        from omni.core.skills import UniversalScriptSkill

        iterations = 3
        latencies = []

        for _ in range(iterations):
            skill = UniversalScriptSkill("git", str(skills_root / "git"))
            start = time.perf_counter()
            await skill.load({"cwd": str(skills_root.parent)})
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print("\n[Performance] Skill Load Time:")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   Min: {min(latencies):.1f}ms")
        print(f"   Max: {max(latencies):.1f}ms")

        # Should load within reasonable time
        assert avg_latency < 500, f"Average load time {avg_latency:.1f}ms exceeds 500ms threshold"
