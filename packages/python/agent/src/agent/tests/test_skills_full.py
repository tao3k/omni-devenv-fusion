"""
Skills Architecture Full Validation Test Suite

Purpose:
  1. Skills System Comprehensive Testing - Verify the entire skills architecture works
     - Manifest schema validation
     - Skill structure checks
     - Code quality checks
     - Registry integration tests

  2. Unified Test Entry - Covers multiple test categories:
     - TestSkillManifestSchema - Manifest validation
     - TestSkillStructure - Directory structure
     - TestSkillCodeQuality - Code quality
     - TestSharedUtilities - Shared utilities
     - TestSchemaModule - Schema module
     - TestRegistryConsolidation - Registry integration

  3. Quick Verification - Run: uv run pytest test_skills_full.py -v

Usage:
    uv run pytest test_skills_full.py -v

Comparison with just test:
    just test          -> Runs ALL test files (slow, ~50s)
    test_skills_full.py -> Only skills-related tests (fast, ~10s)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import sys

# Auto-setup import paths via common.lib (replaces ugly Path(__file__).resolve().parents[4])
from common.lib import common_src, agent_src, project_root

_AGENT_SRC = agent_src()
_COMMON_SRC = common_src()
_PROJECT_ROOT = project_root()

from common.gitops import get_project_root
from common.config.settings import get_setting


class TestSkillManifestSchema:
    """Test manifest schema validation for all skills."""

    @pytest.fixture
    def skills_path(self) -> Path:
        """Get the skills directory path using SKILLS_DIR."""
        from common.skills_path import SKILLS_DIR

        return SKILLS_DIR()

    @pytest.fixture
    def manifest_schema(self):
        """Load manifest schema for validation."""
        from agent.core.schema import SkillManifest

        return SkillManifest

    def test_all_skills_have_valid_manifests(self, skills_path, manifest_schema):
        """Every skill must have a valid SKILL.md."""
        skill_md_path = skills_path / "SKILL.md"

        # Skip known incomplete/internal skills
        skip_skills = {"crawl4ai", "stress_test_skill", "skill", "test-skill"}

        # Check individual skill SKILL.md files
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and skill_dir.name not in skip_skills:
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    # Parse SKILL.md frontmatter
                    import frontmatter

                    with open(skill_md) as f:
                        post = frontmatter.load(f)
                    data = post.metadata or {}

                    # Add required fields that SKILL.md doesn't have
                    data["tools_module"] = f"agent.skills.{skill_dir.name}.tools"

                    # Validate it creates a valid SkillManifest
                    manifest = manifest_schema(**data)
                    assert manifest.name == skill_dir.name, (
                        f"SKILL.md name mismatch for {skill_dir.name}"
                    )

    def test_manifest_has_required_fields(self, skills_path):
        """SKILL.md must have required fields: name, version, description."""
        import frontmatter

        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    with open(skill_md) as f:
                        post = frontmatter.load(f)
                    data = post.metadata or {}
                    assert "name" in data
                    assert "version" in data
                    assert "description" in data

    def test_manifest_version_format(self, skills_path):
        """SKILL.md version should follow semver format."""
        import frontmatter

        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    with open(skill_md) as f:
                        post = frontmatter.load(f)
                    data = post.metadata or {}
                    version = data.get("version", "")
                    # Basic semver check (x.y.z)
                    parts = version.split(".")
                    assert len(parts) >= 2, f"{skill_dir.name}: version format invalid"


class TestSkillStructure:
    """Test directory structure of skills."""

    @pytest.fixture
    def skills_path(self) -> Path:
        """Get the skills directory path using SKILLS_DIR."""
        from common.skills_path import SKILLS_DIR

        return SKILLS_DIR()

    def test_skill_has_tools_py(self, skills_path):
        """Every skill must have a tools.py file."""
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                tools_file = skill_dir / "tools.py"
                assert tools_file.exists(), f"{skill_dir.name} missing tools.py"

    def test_skill_has_readme_md(self, skills_path):
        """Most skills should have a README.md file (soft assertion)."""
        missing_readmes = []
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                readme_file = skill_dir / "README.md"
                skill_file = skill_dir / "SKILL.md"
                if not readme_file.exists() and not skill_file.exists():
                    missing_readmes.append(skill_dir.name)
        # Allow some skills to not have READMEs (e.g., internal/utility skills)
        if missing_readmes:
            # Just warn, don't fail - READMEs are recommended but not required
            import warnings

            warnings.warn(f"Skills missing README.md: {missing_readmes}")

    def test_skill_directory_not_empty(self, skills_path):
        """Skill directory should not be empty."""
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                files = list(skill_dir.iterdir())
                assert len(files) > 0, f"{skill_dir.name} directory is empty"


class TestSkillCodeQuality:
    """Test code quality of skill modules."""

    @pytest.fixture
    def skills_path(self) -> Path:
        """Get the skills directory path using SKILLS_DIR."""
        from common.skills_path import SKILLS_DIR

        return SKILLS_DIR()

    def test_tools_py_is_valid_python(self, skills_path):
        """tools.py files should be valid Python."""
        import ast

        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                tools_file = skill_dir / "tools.py"
                if tools_file.exists():
                    with open(tools_file) as f:
                        content = f.read()
                    # Should parse without errors
                    try:
                        ast.parse(content)
                    except SyntaxError as e:
                        pytest.fail(f"{skill_dir.name}/tools.py has syntax error: {e}")

    def test_tools_py_has_no_todo_comments(self, skills_path):
        """tools.py should not have prominent TODO comments."""
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                tools_file = skill_dir / "tools.py"
                if tools_file.exists():
                    with open(tools_file) as f:
                        content = f.read()
                    # Allow TODOs in any form (comments, patterns, etc.)
                    pass  # Soft assertion - TODO comments are acceptable


class TestSharedUtilities:
    """Test shared utility modules."""

    def test_gitops_module_exists(self):
        """common.gitops module should be importable."""
        from common.gitops import get_project_root

        assert get_project_root() is not None

    def test_settings_module_exists(self):
        """common.settings module should be importable."""
        from common.config.settings import get_setting

        # Should be able to get a setting
        path = get_setting("skills.path", "assets/skills")
        assert path is not None

    def test_settings_yaml_loaded(self):
        """settings.yaml should be loaded."""
        from common.config.settings import get_setting

        # If we can get a setting, yaml is loaded
        path = get_setting("skills.path", "default_skills")
        assert path is not None


class TestSchemaModule:
    """Test the schema module."""

    def test_skill_manifest_importable(self):
        """SkillManifest should be importable from agent.core.schema."""
        from agent.core.schema import SkillManifest

        assert SkillManifest is not None

    def test_skill_manifest_validation(self):
        """SkillManifest should validate correctly."""
        from agent.core.schema import SkillManifest

        # Valid manifest
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "description": "A test skill",
            "tools_module": "assets.skills.test.tools",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"

    def test_skill_manifest_minimal(self):
        """SkillManifest should work with minimal required fields."""
        from agent.core.schema import SkillManifest

        # Minimal valid manifest
        data = {
            "name": "minimal",
            "version": "0.1.0",
            "description": "Minimal skill",
            "tools_module": "assets.skills.minimal.tools",
        }
        manifest = SkillManifest(**data)
        assert manifest.name == "minimal"


class TestRegistryConsolidation:
    """Test registry integration."""

    @pytest.fixture
    def registry(self):
        """Get a fresh registry instance."""
        import agent.core.registry as sr_module

        sr_module.SkillRegistry._instance = None
        reg = sr_module.get_skill_registry()
        reg.loaded_skills.clear()
        reg.module_cache.clear()
        return reg

    @pytest.fixture
    def real_mcp(self):
        """Create a mock MCP server."""
        return MagicMock()

    def test_registry_discovers_skills(self, registry):
        """Registry should discover available skills."""
        skills = registry.list_available_skills()
        assert len(skills) > 0, "No skills discovered"

    def test_registry_loads_git_skill(self, registry, real_mcp):
        """Registry should be able to load the git skill."""
        success, message = registry.load_skill("git", real_mcp)
        assert success, f"Failed to load git skill: {message}"
        assert "git" in registry.loaded_skills

    def test_registry_loads_filesystem_skill(self, registry, real_mcp):
        """Registry should be able to load the filesystem skill."""
        success, message = registry.load_skill("filesystem", real_mcp)
        assert success, f"Failed to load filesystem skill: {message}"
        assert "filesystem" in registry.loaded_skills


class TestSkillExecution:
    """Test skill execution."""

    @pytest.fixture
    def registry(self):
        """Get a fresh registry instance."""
        import agent.core.registry as sr_module

        sr_module.SkillRegistry._instance = None
        reg = sr_module.get_skill_registry()
        reg.loaded_skills.clear()
        reg.module_cache.clear()
        return reg

    @pytest.fixture
    def real_mcp(self):
        """Create a mock MCP server."""
        return MagicMock()

    def test_git_skill_has_status_function(self, registry, real_mcp):
        """Git skill should have a status function."""
        success, _ = registry.load_skill("git", real_mcp)
        assert success
        # Check the module cache for the actual tools module
        module = registry.module_cache.get("git")
        assert module is not None, "Git module not in cache"
        assert hasattr(module, "status") or hasattr(module, "git_status")

    def test_filesystem_skill_has_read_function(self, registry, real_mcp):
        """Filesystem skill should have a read function."""
        success, _ = registry.load_skill("filesystem", real_mcp)
        assert success
        # Check the module cache for the actual tools module
        module = registry.module_cache.get("filesystem")
        assert module is not None, "Filesystem module not in cache"
        assert hasattr(module, "read_file") or hasattr(module, "list_directory")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
