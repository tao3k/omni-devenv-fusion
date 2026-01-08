"""
packages/python/agent/src/agent/tests/test_mcp_dependencies.py
Tests to verify skill architecture dependencies are properly configured.

These tests catch issues like:
- Skill modules failing to import
- Skill registry not discovering skills
- Skills not loading correctly

In uv workspace, packages are installed and can be imported directly.
"""

import pytest
from pathlib import Path


class TestSkillArchitecture:
    """Test that the skill architecture is properly configured."""

    def test_agent_core_imports(self):
        """agent.core modules should import successfully."""
        from agent.core.registry import SkillRegistry

        assert SkillRegistry is not None

    def test_common_mcp_core_imports(self):
        """common.mcp_core modules should import successfully."""
        from common.gitops import get_project_root

        root = get_project_root()
        assert root is not None
        assert root.exists()

    def test_skills_directory_exists(self):
        """assets/skills/ directory should exist with skill modules."""
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        # Check for at least core skills
        core_skills = ["filesystem", "git", "terminal", "testing"]
        for skill in core_skills:
            assert skill in skills, f"Missing skill: {skill}"

    def test_skill_manifests_valid(self):
        """All skill SKILL.md files should be valid YAML frontmatter."""
        from agent.core.registry import get_skill_registry
        import frontmatter

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        for skill_name in skills:
            skill_dir = Path.cwd() / "assets" / "skills" / skill_name
            skill_md_path = skill_dir / "SKILL.md"
            if skill_md_path.exists():
                with open(skill_md_path) as f:
                    data = frontmatter.load(f)
                assert "name" in data.metadata, f"{skill_name} SKILL.md missing 'name'"


class TestSkillRegistry:
    """Test that skill registry can discover and load skills."""

    def test_skill_registry_discovers_skills(self):
        """SkillRegistry should discover all skills in assets/skills/."""
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        required = ["filesystem", "git", "terminal", "testing"]
        for s in required:
            assert s in skills, f"Missing skill: {s}"
