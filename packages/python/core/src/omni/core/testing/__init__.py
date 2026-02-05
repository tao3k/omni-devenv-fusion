"""omni.core.testing - Test Layer Management.

This module provides pytest markers and utilities for categorizing and
executing tests by layer (unit, integration, cloud, etc.).

Example:
    # Mark a test as a unit test
    from omni.core.testing.layers import unit

    @pytest.mark.unit
    def test_something():
        ...

    # Run only unit tests
    pytest tests/units/ -m unit

    # Run all tests except cloud tests
    pytest tests/ -m "not cloud"

    # Run with cloud tests enabled
    pytest tests/ --cloud
"""

from __future__ import annotations

from .layers import (
    # Markers
    unit,
    integration,
    cloud,
    benchmark,
    stress,
    e2e,
    # Utilities
    skip_if_cloud,
    only_cloud,
    get_test_layer,
    # Configuration
    pytest_addoption,
    pytest_configure,
    pytest_collection_modifyitems,
)

__all__ = [
    # Markers
    "unit",
    "integration",
    "cloud",
    "benchmark",
    "stress",
    "e2e",
    # Utilities
    "skip_if_cloud",
    "only_cloud",
    "get_test_layer",
]
