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


class TestDiscoverTool:
    """Tests for the discover tool."""

    def test_discover_is_callable(self):
        """Test that discover is a callable async function."""
        from skill.scripts import discovery
        import inspect

        assert callable(discovery.discover)
        assert inspect.iscoroutinefunction(discovery.discover)

    def test_discover_has_skill_command_attr(self):
        """Test that discover has _is_skill_command attribute."""
        from skill.scripts import discovery

        assert getattr(discovery.discover, "_is_skill_command", False) is True

    def test_discover_has_skill_config(self):
        """Test that discover has _skill_config with name 'discover'."""
        from skill.scripts import discovery

        config = getattr(discovery.discover, "_skill_config", None)
        assert config is not None
        assert config.get("name") == "discover"

    def test_discover_category_is_system(self):
        """Test that discover has category 'system'."""
        from skill.scripts import discovery

        config = getattr(discovery.discover, "_skill_config", None)
        assert config is not None
        assert config.get("category") == "system"

    def test_discover_description_contains_critical(self):
        """Test that discover description contains '[CRITICAL]' marker."""
        from skill.scripts import discovery

        config = getattr(discovery.discover, "_skill_config", None)
        assert config is not None
        assert "[CRITICAL]" in config.get("description", "")

    def test_discover_description_contains_when_to_use(self):
        """Test that discover description contains 'WHEN TO USE' section."""
        from skill.scripts import discovery

        config = getattr(discovery.discover, "_skill_config", None)
        assert config is not None
        assert "WHEN TO USE" in config.get("description", "")

    def test_discover_description_mentions_intent(self):
        """Test that discover description mentions 'intent' parameter."""
        from skill.scripts import discovery

        config = getattr(discovery.discover, "_skill_config", None)
        assert config is not None
        assert "intent" in config.get("description", "").lower()

    def test_suggest_was_removed(self):
        """Test that suggest tool has been removed (replaced by discover)."""
        from skill.scripts import discovery

        assert not hasattr(discovery, "suggest"), "suggest should be removed - use discover instead"

    def test_discover_returns_dict(self):
        """Test that discover function signature returns dict."""
        from skill.scripts import discovery
        import inspect

        sig = inspect.signature(discovery.discover)
        # The return annotation should be dict[str, Any]
        return_annotation = str(sig.return_annotation)
        assert "dict" in return_annotation or "Dict" in return_annotation


class TestSkillDiscoveryService:
    """Tests for the SkillDiscoveryService.search_tools method."""

    def test_search_tools_finds_results(self):
        """Test that search_tools returns results for 'read file'."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools(query="read file", limit=3)

        # Should find at least one tool related to reading files
        assert len(matches) > 0

    def test_search_tools_returns_toolmatch_objects(self):
        """Test that search_tools returns ToolMatch objects."""
        from omni.core.skills.discovery import SkillDiscoveryService, ToolMatch

        service = SkillDiscoveryService()
        matches = service.search_tools(query="git commit", limit=3)

        for m in matches:
            assert isinstance(m, ToolMatch)
            assert m.name
            assert m.skill_name
            assert m.score > 0

    def test_search_tools_sorted_by_score(self):
        """Test that results are sorted by score (highest first)."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools(query="run tests", limit=5)

        if len(matches) >= 2:
            for i in range(len(matches) - 1):
                assert matches[i].score >= matches[i + 1].score

    def test_search_tools_has_usage_template(self):
        """Test that results have usage_template."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools(query="git status", limit=3)

        for m in matches:
            assert m.usage_template
            assert "..." in m.usage_template or "()" in m.usage_template

    def test_search_tools_with_limit(self):
        """Test that limit parameter works correctly."""
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools(query="file", limit=2)

        assert len(matches) <= 2

    def test_search_tools_returns_discover_as_fallback(self):
        """Test that search_tools returns skill.discover as fallback for unknown queries.

        This implements the "Discovery First" rule - skill.discover is always
        available as a fallback when no specific tool matches.
        """
        from omni.core.skills.discovery import SkillDiscoveryService

        service = SkillDiscoveryService()
        matches = service.search_tools(query="xyznonexistenttool123", limit=3)

        # skill.discover should always be returned as fallback
        assert len(matches) > 0
        # skill.discover should be in results (as fallback)
        assert any(m.name == "skill.discover" for m in matches)


class TestSkillCommands:
    """Test skill management commands work correctly."""

    def test_discover_is_callable(self):
        """Test that discover is a callable function."""
        from skill.scripts import discovery

        assert callable(discovery.discover)

    def test_list_templates_requires_skill_name(self):
        """Test that list_templates requires skill_name parameter."""
        import inspect

        from skill.scripts import templates

        sig = inspect.signature(templates.list_templates)
        assert "skill_name" in sig.parameters

    def test_has_expected_commands(self):
        """Test that discovery has expected number of public functions."""
        from skill.scripts import discovery

        commands = [attr for attr in dir(discovery) if not attr.startswith("_")]
        # After removing suggest, we should have discover, jit_install, list_index
        assert len(commands) >= 3
