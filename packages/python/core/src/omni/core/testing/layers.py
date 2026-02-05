"""Test Layer Markers and Configuration.

This module defines pytest markers for categorizing tests by execution layer.

Test Layers:
    - unit: Fast, isolated tests (local execution)
    - integration: Tests requiring multiple components
    - cloud: Tests requiring external services (skipped locally)
    - benchmark: Performance benchmarking tests
    - stress: Stress/load tests (long-running)
    - e2e: End-to-end user workflow tests

Usage:
    pytest packages/python/core/tests/units/ -m "unit"      # Run only unit tests
    pytest packages/python/core/tests/ -m "integration"    # Run integration tests
    pytest packages/python/core/tests/ --ignore-glob="*cloud*" -m "not cloud"  # Skip cloud tests
"""

from __future__ import annotations

import pytest


# =============================================================================
# Test Layer Markers
# =============================================================================

# Unit tests - Fast, isolated, no external dependencies
# Target: < 100ms per test, mock all external calls
unit = pytest.mark.unit(reason="Unit test: Fast, isolated, mocked dependencies")

# Integration tests - Multiple components, real interactions
# Target: < 1s per test, may use real implementations
integration = pytest.mark.integration(
    reason="Integration test: Multiple components, real interactions"
)

# Cloud tests - Require external services, run in CI
# Skipped by default, use --cloud flag to enable
cloud = pytest.mark.cloud(reason="Cloud test: Requires external services, skipped locally")

# Benchmark tests - Performance measurement
# Run separately: pytest --benchmark-only
benchmark = pytest.mark.benchmark(reason="Benchmark test: Performance measurement")

# Stress tests - Long-running, resource-intensive
# Run separately: pytest -m "stress"
stress = pytest.mark.stress(reason="Stress test: Long-running, resource-intensive")

# End-to-end tests - Complete user workflows
# Run separately: pytest -m "e2e"
e2e = pytest.mark.e2e(reason="End-to-end test: Complete user workflow")


# =============================================================================
# Custom Pytest Options
# =============================================================================


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--cloud",
        action="store_true",
        default=False,
        help="Run cloud tests (requires external services)",
    )
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Run only fast tests (unit tests only)",
    )
    parser.addoption(
        "--all-tests",
        action="store_true",
        default=False,
        help="Run all tests including slow/cloud tests",
    )


def pytest_configure(config):
    """Configure pytest with custom markers and options."""
    # Register markers
    config.addinivalue_line("markers", "unit: Fast, isolated tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Tests with multiple real components")
    config.addinivalue_line("markers", "cloud: Tests requiring external services (CI only)")
    config.addinivalue_line("markers", "benchmark: Performance benchmarking tests")
    config.addinivalue_line("markers", "stress: Long-running stress/load tests")
    config.addinivalue_line("markers", "e2e: End-to-end user workflow tests")

    # Store flags for use in collection
    config.cloud_enabled = config.getoption("--cloud", default=False)
    config.fast_mode = config.getoption("--fast", default=False)
    config.all_tests = config.getoption("--all-tests", default=False)


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on layer markers and flags."""
    cloud_enabled = getattr(config, "cloud_enabled", False)
    fast_mode = getattr(config, "fast_mode", False)
    all_tests = getattr(config, "all_tests", False)

    filtered_items = []

    for item in items:
        # Check if test has cloud marker
        cloud_marker = item.get_closest_marker("cloud")
        if cloud_marker and not cloud_enabled and not all_tests:
            # Skip cloud tests unless --cloud or --all-tests is set
            continue

        # Check for --fast mode (unit tests only)
        if fast_mode:
            unit_marker = item.get_closest_marker("unit")
            if not unit_marker:
                # Also skip tests without any layer marker in fast mode
                continue

        filtered_items.append(item)

    items[:] = filtered_items


# =============================================================================
# Skip Helpers
# =============================================================================


def skip_if_cloud(reason: str = "Test requires external services"):
    """Decorator to skip test in cloud mode."""
    return pytest.mark.skipif(
        condition=not getattr(pytest, "CLOUD_ENABLED", False),
        reason=f"{reason} (use --cloud to run)",
    )


def only_cloud(reason: str = "Test only runs in cloud mode"):
    """Decorator to only run test in cloud mode."""
    return pytest.mark.skipif(condition=getattr(pytest, "CLOUD_ENABLED", True), reason=reason)


# =============================================================================
# Test Discovery Patterns
# =============================================================================

# Directory structure expectations:
TEST_DIRS = {
    "unit": ["tests/units/", "tests/unit/", "tests/test_*.py"],
    "integration": ["tests/integration/", "tests/int_*.py"],
    "cloud": ["tests/cloud/", "tests/remote/", "tests/*_cloud.py"],
    "benchmark": ["tests/benchmarks/", "tests/*_benchmark.py"],
    "stress": ["tests/stress/", "tests/*_stress.py"],
    "e2e": ["tests/e2e/", "tests/*_e2e.py"],
}


def get_test_layer(test_path: str) -> str:
    """Determine the test layer based on file path."""
    import re

    for layer, patterns in TEST_DIRS.items():
        for pattern in patterns:
            # Convert glob pattern to regex
            regex_pattern = pattern.replace("*", ".*")
            if re.search(regex_pattern, test_path):
                return layer

    return "unknown"
