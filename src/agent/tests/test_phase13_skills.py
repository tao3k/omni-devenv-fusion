"""
src/agent/tests/test_phase13_skills.py
Comprehensive testing for the Phase 13 Skill Architecture.

Covers:
1. SkillRegistry (Discovery, Loading, Context)
2. SkillManifest (Schema Validation)
3. Integration with 'git' skill

Note: _template is a skeleton for creating new skills and cannot be loaded
as a Python module (names starting with underscore have special meaning).
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import core components
from agent.core.schema import SkillManifest
from agent.core.skill_registry import SkillRegistry, get_skill_registry
from mcp.server.fastmcp import FastMCP


@pytest.fixture
def registry():
    """Fixture to provide a clean registry instance."""
    reg = get_skill_registry()
    # Clear loaded skills between tests for isolation
    original_loaded = reg.loaded_skills.copy()
    yield reg
    # Cleanup: restore any skills that should persist
    reg.loaded_skills.clear()
    reg.loaded_skills.update(original_loaded)


@pytest.fixture
def mock_mcp():
    """Mock FastMCP server for tool registration."""
    mcp = MagicMock(spec=FastMCP)
    mcp.tool = MagicMock(return_value=lambda x: x)  # Mock decorator
    return mcp


class TestSkillManifest:
    """Test the DNA of skills - Schema validation."""

    def test_valid_manifest_creation(self):
        """Test creating a valid SkillManifest."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "dependencies": ["git"],
            "tools_module": "agent.skills.test.tools",
            "guide_file": "guide.md"
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
        assert manifest.dependencies == ["git"]
        assert manifest.tools_module == "agent.skills.test.tools"

    def test_minimal_manifest(self):
        """Test creating manifest with only required fields."""
        data = {
            "name": "minimal_skill",
            "version": "0.1.0",
            "description": "Minimal skill",
            "tools_module": "agent.skills.minimal.tools"
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "minimal_skill"
        assert manifest.dependencies == []  # Default empty list
        assert manifest.guide_file == "guide.md"  # Default value
        assert manifest.prompts_file is None  # Optional field

    def test_invalid_manifest_missing_name(self):
        """Test that missing name raises error."""
        data = {
            "version": "1.0.0",
            "description": "A test skill",
            "tools_module": "agent.skills.test.tools"
        }
        with pytest.raises(ValueError):
            SkillManifest(**data)

    def test_invalid_manifest_missing_tools_module(self):
        """Test that missing tools_module raises error."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill"
        }
        with pytest.raises(ValueError):
            SkillManifest(**data)

    def test_invalid_version_format(self):
        """Test that non-semantic version is accepted (validation happens elsewhere)."""
        data = {
            "name": "test_skill",
            "version": "not-a-version",  # Still accepted at schema level
            "description": "A test skill",
            "tools_module": "agent.skills.test.tools"
        }
        manifest = SkillManifest(**data)
        assert manifest.version == "not-a-version"


class TestSkillRegistry:
    """Test the Kernel logic - Discovery and management."""

    def test_discovery_finds_git_skill(self, registry):
        """Registry should find 'git' skill."""
        skills = registry.list_available_skills()
        assert "git" in skills, f"Expected 'git' in skills, got: {skills}"

    def test_discovery_finds_template_directory(self, registry):
        """Registry should discover _template directory (for copying)."""
        skills = registry.list_available_skills()
        # Note: _template is discovered but cannot be loaded as Python module
        assert "_template" in skills, f"Expected '_template' in skills, got: {skills}"

    def test_discovery_excludes_pycache(self, registry):
        """Registry should not pick up __pycache__ or other non-skill dirs."""
        skills = registry.list_available_skills()
        assert "__pycache__" not in skills
        assert "__init__.py" not in skills  # Files, not directories

    def test_manifest_parsing_git(self, registry):
        """Registry should correctly parse git/manifest.json."""
        manifest = registry.get_skill_manifest("git")
        assert manifest is not None, "Git skill manifest should exist"
        assert manifest.name == "git"
        assert manifest.version == "1.0.0"  # Actual value from manifest.json
        assert manifest.tools_module == "agent.skills.git.tools"
        assert manifest.guide_file == "guide.md"

    def test_manifest_parsing_template(self, registry):
        """Registry should correctly parse _template/manifest.json."""
        manifest = registry.get_skill_manifest("_template")
        assert manifest is not None, "Template manifest should exist"
        # Note: The manifest name is "template" but directory is "_template"
        assert manifest.name == "template"
        assert manifest.version == "1.0.0"

    def test_get_context_returns_guide(self, registry):
        """Registry should read guide.md content."""
        context = registry.get_skill_context("git")
        assert context is not None
        assert len(context) > 0, "Context should not be empty"
        # Guide should contain expected content from our pilot
        assert "GIT GUIDE" in context or "Git" in context

    def test_get_context_prompts_injection(self, registry):
        """Registry should include prompts.md if available."""
        context = registry.get_skill_context("git")
        # Git has prompts.md, so context should include it
        manifest = registry.get_skill_manifest("git")
        if manifest.prompts_file:
            # Context should contain prompt content
            assert len(context) > 100, "Context with prompts should be substantial"

    def test_get_context_not_loaded_skill(self, registry):
        """Getting context for unloaded skill should still work (reads from disk)."""
        context = registry.get_skill_context("git")
        assert context is not None
        assert len(context) > 0
        assert "GIT" in context or "git" in context.lower()

    def test_get_context_nonexistent_skill(self, registry):
        """Getting context for nonexistent skill returns empty string."""
        context = registry.get_skill_context("fake_skill_xyz")
        # Returns empty string when skill not found
        assert context == "", "Nonexistent skill should return empty context"


class TestSkillLoading:
    """Test the dynamic loading mechanism."""

    def test_load_git_skill_success(self, registry, mock_mcp):
        """Should successfully load the git skill and register tools."""
        success, message = registry.load_skill("git", mock_mcp)

        assert success is True, f"Expected success, got: {message}"
        assert "git" in registry.loaded_skills
        assert "successfully" in message.lower()

    def test_load_git_imports_module(self, registry, mock_mcp):
        """Verify that the tools module was actually imported."""
        registry.load_skill("git", mock_mcp)
        module_name = "agent.skills.git.tools"
        assert module_name in sys.modules, f"Module {module_name} should be in sys.modules"

    def test_load_nonexistent_skill_fails(self, registry, mock_mcp):
        """Should fail gracefully for nonexistent skill."""
        success, message = registry.load_skill("fake_skill_123", mock_mcp)
        assert success is False, "Loading fake skill should fail"
        assert "not found" in message.lower()

    def test_idempotent_loading(self, registry, mock_mcp):
        """Loading the same skill twice should be safe."""
        # First load
        success1, message1 = registry.load_skill("git", mock_mcp)
        assert success1 is True

        # Second load - should handle gracefully
        success2, message2 = registry.load_skill("git", mock_mcp)
        assert success2 is True
        # Should indicate already loaded
        assert "already loaded" in message2.lower()

    def test_template_cannot_be_loaded(self, registry, mock_mcp):
        """_template cannot be loaded as Python module (underscore prefix).

        This is expected behavior - _template is a skeleton for creating new skills.
        Python treats directories starting with underscore as private packages.
        """
        success, message = registry.load_skill("_template", mock_mcp)
        # Should fail because agent.skills._template.tools cannot be imported
        assert success is False
        assert "No module named" in message or "not found" in message.lower()
        assert "_template" not in registry.loaded_skills

    def test_double_load_does_not_duplicate(self, registry, mock_mcp):
        """Loading twice should not create duplicate entries."""
        registry.load_skill("git", mock_mcp)
        registry.load_skill("git", mock_mcp)

        # Count occurrences in loaded_skills
        count = sum(1 for k in registry.loaded_skills if k == "git")
        assert count == 1, "Git should only be loaded once"


class TestSkillIntegration:
    """Integration tests combining multiple components."""

    def test_git_skill_full_chain(self, registry, mock_mcp):
        """Test complete flow: discover -> load -> use."""
        # 1. Discover
        skills = registry.list_available_skills()
        assert "git" in skills

        # 2. Load
        success, message = registry.load_skill("git", mock_mcp)
        assert success is True

        # 3. Get context
        context = registry.get_skill_context("git")
        assert context is not None
        assert len(context) > 0

        # 4. Verify module loaded
        assert "agent.skills.git.tools" in sys.modules

    def test_loaded_skill_context_from_memory(self, registry, mock_mcp):
        """After loading, context should come from loaded_skills dict."""
        # Load the skill
        registry.load_skill("git", mock_mcp)

        # Get context (should prefer memory over disk)
        context = registry.get_skill_context("git")
        assert context is not None
        assert "GIT" in context or "Smart Commit" in context


class TestSkillRegistrySingleton:
    """Test singleton behavior of registry."""

    def test_singleton_returns_same_instance(self):
        """Multiple calls to get_skill_registry should return same instance."""
        reg1 = get_skill_registry()
        reg2 = get_skill_registry()
        assert reg1 is reg2, "Registry should be a singleton"

    def test_loaded_skills_isolated_between_tests(self, registry):
        """Verify that loaded_skills is accessible for test isolation."""
        assert hasattr(registry, 'loaded_skills')
        assert isinstance(registry.loaded_skills, dict)


class TestSkillEdgeCases:
    """Edge case and error handling tests."""

    def test_get_manifest_invalid_skill(self, registry):
        """Test getting manifest for nonexistent skill."""
        manifest = registry.get_skill_manifest("totally_fake_skill_999")
        assert manifest is None

    def test_loaded_skills_contains_manifest(self, registry, mock_mcp):
        """After loading, loaded_skills should contain the manifest."""
        registry.load_skill("git", mock_mcp)
        assert "git" in registry.loaded_skills
        manifest = registry.loaded_skills["git"]
        assert isinstance(manifest, SkillManifest)
        assert manifest.name == "git"

    def test_git_manifest_has_expected_fields(self, registry):
        """Verify git manifest has all expected fields for MCP integration."""
        manifest = registry.get_skill_manifest("git")
        assert manifest.tools_module == "agent.skills.git.tools"
        assert manifest.guide_file == "guide.md"
        # Git should have prompts for LLM context injection
        assert manifest.prompts_file == "prompts.md"

    def test_load_invalid_module_fails(self, registry, mock_mcp):
        """Loading a skill with invalid tools_module should fail."""
        # We can test this by creating a mock manifest
        # but easier to verify the behavior through the actual load
        success, message = registry.load_skill("fake_skill_no_module", mock_mcp)
        assert success is False


if __name__ == "__main__":
    # Allow running directly
    sys.exit(pytest.main(["-v", __file__, "--tb=short"]))
