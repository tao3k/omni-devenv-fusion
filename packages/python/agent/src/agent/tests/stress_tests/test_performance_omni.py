"""
Performance benchmarks for Omni One Tool Architecture.

These tests measure the dispatch latency and throughput of the
single 'omni' tool. They are intentionally slower than unit tests
and should be run separately.

Usage:
    just test-stress
    uv run pytest stress_tests/test_performance_omni.py -v
"""

import pytest
import time
import sys
from pathlib import Path

# Import omni helper (Phase 35.3)
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_skills import omni


class TestOmniPerformance:
    """Performance benchmarks for Phase 25 One Tool architecture."""

    @pytest.mark.asyncio
    async def test_omni_dispatch_latency(self):
        """Measure @omni dispatch latency."""
        iterations = 5
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = await omni("git.status")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        print(f"\nOmni Dispatch Latency:")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   Min: {min(latencies):.1f}ms")
        print(f"   Max: {max(latencies):.1f}ms")

        # Should be under 100ms for local commands
        assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms exceeds 100ms threshold"
