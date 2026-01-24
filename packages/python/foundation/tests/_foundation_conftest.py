"""
Foundation Test Configuration

Shared fixtures for omni.foundation tests.
"""

import sys
from pathlib import Path

import pytest

# Ensure omni.foundation is importable
_foundation_path = Path(__file__).parent.parent.parent
if str(_foundation_path) not in sys.path:
    sys.path.insert(0, str(_foundation_path))


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
    # Try to detect from git, fall back to current directory structure
    from omni.foundation.runtime.gitops import get_project_root

    return get_project_root()


@pytest.fixture(scope="session")
def skills_dir(project_root):
    """Get skills directory."""
    from omni.foundation.config.skills import SKILLS_DIR

    return SKILLS_DIR()


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create a temporary skills directory structure."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "git").mkdir()
    (skills_dir / "python").mkdir()
    return skills_dir


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".omni"
    config_dir.mkdir()
    return config_dir


@pytest.fixture(autouse=True)
def mock_rust_bridge():
    """Mock the Rust bridge for tests that don't have Rust compiled."""
    try:
        import omni_core_rs

        yield
    except ImportError:
        # Create a mock module
        import types

        mock_module = types.ModuleType("omni_core_rs")

        # Add common functions used in tests
        mock_module.get_file_hash = lambda x: "mock_hash"
        mock_module.scan_directory = lambda x: []

        sys.modules["omni_core_rs"] = mock_module
        try:
            yield
        finally:
            del sys.modules["omni_core_rs"]
