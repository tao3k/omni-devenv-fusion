"""
Skill Management Tests - Trinity Architecture v2.0

Tests for skill management commands using direct script imports.
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestSkillScripts:
    """Test skill management scripts can be imported."""

    def test_discovery_script_imports(self):
        """Test discover command is available."""
        from skill.scripts import discovery

        assert hasattr(discovery, "discover")

    def test_templates_script_imports(self):
        """Test templates module imports successfully."""
        from skill.scripts import templates

        assert hasattr(templates, "list_templates")

    def test_reload_script_imports(self):
        """Test reload_skill command is available."""
        from skill.scripts import reload as reload_module

        assert hasattr(reload_module, "reload_skill")

    def test_unload_script_imports(self):
        """Test unload_skill command is available."""
        from skill.scripts import unload

        assert hasattr(unload, "unload_skill")


class TestSkillCommands:
    """Test skill management commands work correctly."""

    def test_discover_is_callable(self):
        """Test that discover is a callable function."""
        from skill.scripts import discovery

        assert callable(discovery.discover)

    def test_list_templates_requires_skill_name(self):
        """Test that list_templates requires skill_name parameter."""
        from skill.scripts import templates
        import inspect

        sig = inspect.signature(templates.list_templates)
        assert "skill_name" in sig.parameters

    def test_has_expected_commands(self):
        """Test that discovery has expected number of public functions."""
        from skill.scripts import discovery

        commands = [attr for attr in dir(discovery) if not attr.startswith("_")]
        assert len(commands) >= 3  # At least discover, jit_install, etc.
