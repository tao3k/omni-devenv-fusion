"""Omni Test Kit - Pytest plugin registration.

This module registers all fixtures, markers, and hooks for the Omni Test Kit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omni.test_kit.decorators import load_test_cases
from omni.test_kit.skill import ensure_skills_import_path
from omni.foundation.config.dirs import get_skills_dir

# Register fixtures from submodules
pytest_plugins = [
    "omni.test_kit.fixtures.memory_protection",  # Must load early: memory cap + per-test abort
    "omni.test_kit.fixtures",
    "omni.test_kit.mcp",
    "omni.test_kit.langgraph",
    "omni.test_kit.core",
]


def pytest_load_initial_conftests(early_config, parser, args):
    """Hook to set up environment before tests start.

    Adds configured skills directory to sys.path for skill tests.
    """
    ensure_skills_import_path(get_skills_dir())


def pytest_generate_tests(metafunc):
    """Custom parametrization logic for Omni Test Kit.

    Handles @data_driven marker by loading files relative to the test module.
    """
    marker = metafunc.definition.get_closest_marker("omni_data_driven")
    if marker:
        data_path = marker.kwargs.get("data_path")
        if data_path:
            test_dir = Path(metafunc.module.__file__).parent
            full_path = test_dir / data_path

            cases = load_test_cases(str(full_path))
            if cases:
                metafunc.parametrize("case", cases, ids=[c.name for c in cases])


def pytest_configure(config):
    """Register markers and make assertions available."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "omni_data_driven: mark tests for data-driven execution with Omni test-kit"
    )
    config.addinivalue_line("markers", "omni_skill: mark tests for a specific Omni skill")

    # Register testing layer markers
    config.addinivalue_line("markers", "unit: Fast, isolated tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Tests with multiple real components")
    config.addinivalue_line("markers", "cloud: Tests requiring external services (CI only)")
    config.addinivalue_line("markers", "benchmark: Performance benchmarking tests")
    config.addinivalue_line("markers", "stress: Long-running stress/load tests")
    config.addinivalue_line("markers", "e2e: End-to-end user workflow tests")

    # Make asserts available globally for pytest assertions
    config.option.assertion_mode = "rewrite"


# =============================================================================
# Testing Layer Markers (for use with pytest.mark)
# =============================================================================


def unit(func):
    """Mark test as a unit test (fast, isolated, mocked dependencies)."""
    return pytest.mark.unit(func)


def integration(func):
    """Mark test as an integration test (multiple components, real interactions)."""
    return pytest.mark.integration(func)


def cloud(func):
    """Mark test as a cloud test (requires external services)."""
    return pytest.mark.cloud(func)


def benchmark(func):
    """Mark test as a benchmark test (performance measurement)."""
    return pytest.mark.benchmark(func)


def stress(func):
    """Mark test as a stress test (long-running, resource-intensive)."""
    return pytest.mark.stress(func)


def e2e(func):
    """Mark test as an end-to-end test (complete user workflow)."""
    return pytest.mark.e2e(func)
