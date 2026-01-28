"""
conftest.py - Benchmark Test Configuration

Benchmark tests require pytest-benchmark plugin which is incompatible with
pytest-xdist parallel execution. This module provides conditional handling.

Run benchmarks with:
    uv run pytest packages/python/core/tests/benchmarks/ -v --benchmark-only -n 0
"""

from __future__ import annotations

import pytest


# Register custom marker for benchmark tests
def pytest_configure(config):
    """Register benchmark marker."""
    config.addinivalue_line("markers", "benchmark: marks tests that require pytest-benchmark")


def pytest_collection_modifyitems(config, items):
    """
    Skip benchmark tests when pytest-benchmark plugin is not available.

    The benchmark plugin is intentionally disabled in pyproject.toml for
    compatibility with pytest-xdist parallel execution.
    """
    # Check if benchmark plugin is available
    benchmark_available = config.pluginmanager.has_plugin("benchmark")

    if not benchmark_available:
        # Filter out all benchmark tests
        remaining = []
        for item in items:
            # Check if test has benchmark marker
            if item.get_closest_marker("benchmark"):
                item.add_marker(pytest.mark.skip(reason="pytest-benchmark plugin is required"))
            remaining.append(item)
