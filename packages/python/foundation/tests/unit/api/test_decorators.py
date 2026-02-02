"""
Agent Tests - Decorator Validation Tests

Validates @skill_command decorator correctness using core skill scripts.
"""

import sys
import pytest
from pathlib import Path
from omni.foundation.config.skills import SKILLS_DIR


def load_skill_script(skill_name: str, script_name: str):
    """Load a specific skill script for testing."""
    import importlib.util

    script_path = SKILLS_DIR(skill_name) / "scripts" / f"{script_name}.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    module_name = f"test_{skill_name}_{script_name}"
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSkillScriptDecorators:
    """Test @skill_command decorator functionality on real scripts."""

    @pytest.fixture
    def discovery_module(self):
        """Load skill discovery script."""
        return load_skill_script("skill", "discovery")

    def test_discover_has_marker(self, discovery_module):
        """discover command should have _is_skill_command marker."""
        assert hasattr(discovery_module.discover, "_is_skill_command")
        assert discovery_module.discover._is_skill_command is True

    def test_discover_has_config(self, discovery_module):
        """discover command should have _skill_config with name and category."""
        assert hasattr(discovery_module.discover, "_skill_config")
        config = discovery_module.discover._skill_config
        assert config["name"] == "discover"
        assert config["category"] == "system"

    def test_jit_install_has_marker(self, discovery_module):
        """jit_install should have _is_skill_command marker."""
        assert hasattr(discovery_module.jit_install, "_is_skill_command")
        assert discovery_module.jit_install._is_skill_command is True
