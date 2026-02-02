"""Core test fixtures - paths, tracing, and utilities."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from omni.test_kit.logging import TestTracer, setup_test_logging


@pytest.fixture(scope="session", autouse=True)
def _test_logging():
    setup_test_logging()


@pytest.fixture
def test_tracer(request):
    """Fixture to provide a TestTracer instance."""
    return TestTracer(request.node.name)


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory using git toplevel."""
    from omni.foundation.runtime.gitops import get_project_root

    root = get_project_root()
    assert root.exists(), f"Project root not found: {root}"
    return root


@pytest.fixture
def skills_root() -> Path:
    """Get the skills root directory (assets/skills)."""
    from omni.foundation.config.skills import SKILLS_DIR

    skills = SKILLS_DIR()
    assert skills.exists(), f"Skills directory not found: {skills}"
    return skills


@pytest.fixture
def config_dir() -> Path:
    """Get the config directory (PRJ_CONFIG_HOME)."""
    from omni.foundation.config.dirs import PRJ_DIRS

    return PRJ_DIRS.config_home


@pytest.fixture
def cache_dir() -> Path:
    """Get the cache directory (PRJ_CACHE_HOME)."""
    from omni.foundation.config.dirs import PRJ_DIRS

    return PRJ_DIRS.cache_home


@pytest.fixture(autouse=True)
def mock_rust_bridge():
    """Mock the Rust bridge for tests that don't have Rust compiled."""
    try:
        import omni_core_rs

        yield
    except ImportError:
        # Create a mock module
        mock_module = types.ModuleType("omni_core_rs")
        # Add common functions used in tests
        mock_module.get_file_hash = lambda x: "mock_hash"
        mock_module.scan_directory = lambda x: []
        mock_module.PyCheckpointStore = MagicMock()
        mock_module.create_checkpoint_store = MagicMock()

        sys.modules["omni_core_rs"] = mock_module
        try:
            yield
        finally:
            del sys.modules["omni_core_rs"]


@pytest.fixture
def clean_settings():
    """
    Fixture that resets Settings singleton before and after test.
    Returns a fresh Settings instance.
    """
    from omni.foundation.config.settings import Settings

    # Save original state
    original_instance = Settings._instance
    original_loaded = Settings._loaded

    # Reset
    Settings._instance = None
    Settings._loaded = False

    yield Settings()

    # Restore
    Settings._instance = original_instance
    Settings._loaded = original_loaded


@pytest.fixture
def mock_agent_context():
    ctx = MagicMock()
    ctx.memory = MagicMock()
    ctx.logger = MagicMock()
    return ctx
