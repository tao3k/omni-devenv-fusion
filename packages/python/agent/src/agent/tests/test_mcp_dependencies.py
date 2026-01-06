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
import json
from pathlib import Path


class TestSkillArchitecture:
    """Test that the skill architecture is properly configured."""

    def test_agent_core_imports(self):
        """agent.core modules should import successfully."""
        from agent.core.skill_registry import SkillRegistry

        assert SkillRegistry is not None

    def test_common_mcp_core_imports(self):
        """common.mcp_core modules should import successfully."""
        from common.gitops import get_project_root

        root = get_project_root()
        assert root is not None
        assert root.exists()

    def test_skills_directory_exists(self):
        """assets/skills/ directory should exist with skill modules."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        # Check for at least core skills
        core_skills = ["filesystem", "git", "terminal", "testing"]
        for skill in core_skills:
            assert skill in skills, f"Missing skill: {skill}"

    def test_skill_manifests_valid(self):
        """All skill manifest.json files should be valid JSON."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        for skill_name in skills:
            skill_dir = Path.cwd() / "agent" / "skills" / skill_name
            manifest_path = skill_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    data = json.load(f)
                assert "name" in data, f"{skill_name} manifest missing 'name'"
                has_tools = "tools_module" in data or "tools" in data
                assert has_tools, f"{skill_name} manifest missing 'tools_module' or 'tools'"


class TestSkillRegistry:
    """Test that skill registry can discover and load skills."""

    def test_skill_registry_discovers_skills(self):
        """SkillRegistry should discover all skills in assets/skills/."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        skills = registry.list_available_skills()

        required = ["filesystem", "git", "terminal", "testing"]
        for s in required:
            assert s in skills, f"Missing skill: {s}"
