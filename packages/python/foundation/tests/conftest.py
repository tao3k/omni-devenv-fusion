"""
Foundation Test Configuration

Shared fixtures for omni.foundation tests.
"""

import sys
from pathlib import Path
import pytest

# Ensure omni.foundation is importable if running independently
_foundation_path = Path(__file__).parent.parent.parent
if str(_foundation_path) not in sys.path:
    sys.path.insert(0, str(_foundation_path))


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
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
