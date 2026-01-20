"""
Pytest plugin to synchronize polyfactory seed with pytest-randomly.

This ensures deterministic test data generation by using the same seed
that pytest-randomly sets for test order.
"""

import pytest
import random


def pytest_configure(config):
    """Configure pytest-randomly integration."""
    pass  # Plugin registration happens automatically by pytest-randomly


@pytest.fixture(autouse=True)
def sync_polyfactory_seed():
    """Ensure polyfactory uses pytest-randomly seed for deterministic test data.

    Note: This fixture is autouse=True to ensure consistent test data generation
    across all tests. The seed is automatically set by pytest-randomly.
    """
    import pytest_randomly

    seed = getattr(pytest_randomly, "current_test_random_seed", None)
    if seed is not None:
        random.seed(seed)
    yield seed
