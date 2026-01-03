"""
src/agent/tests/test_mcp_dependencies.py
Tests to verify skill architecture dependencies are properly configured.

These tests catch issues like:
- Skill modules failing to import
- Skill registry not discovering skills
- Skills not loading correctly
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestSkillArchitecture:
    """Test that the skill architecture is properly configured."""

    def test_agent_core_imports(self):
        """agent.core modules should import successfully."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from agent.core.skill_registry import SkillRegistry; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"agent.core.skill_registry import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_common_mcp_core_imports(self):
        """common.mcp_core modules should import successfully."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from common.mcp_core.gitops import get_project_root; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"common.mcp_core.gitops import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_skills_directory_exists(self):
        """agent/skills/ directory should exist with skill modules."""
        skills_path = Path(__file__).parent.parent.parent.parent / "agent/skills"
        assert skills_path.exists(), "agent/skills/ directory should exist"

        # Check for at least core skills
        core_skills = ["filesystem", "git", "terminal", "testing"]
        for skill in core_skills:
            skill_path = skills_path / skill
            assert skill_path.exists(), f"Skill {skill} should exist at {skill_path}"

    def test_skill_manifests_valid(self):
        """All skill manifest.json files should be valid JSON."""
        import json

        skills_path = Path(__file__).parent.parent.parent.parent / "agent/skills"
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                manifest_path = skill_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        data = json.load(f)
                    assert "name" in data, f"{skill_dir.name} manifest missing 'name'"
                    # New format uses tools_module, legacy format uses tools
                    has_tools = "tools_module" in data or "tools" in data
                    assert has_tools, f"{skill_dir.name} manifest missing 'tools_module' or 'tools'"


class TestSkillRegistry:
    """Test that skill registry can discover and load skills."""

    def test_skill_registry_discovers_skills(self):
        """SkillRegistry should discover all skills in agent/skills/."""
        result = subprocess.run(
            ["uv", "run", "python", "-c", """
import sys
sys.path.insert(0, 'src')
from agent.core.skill_registry import get_skill_registry
registry = get_skill_registry()
skills = registry.list_available_skills()
required = ['filesystem', 'git', 'terminal', 'testing']
for s in required:
    assert s in skills, f'Missing skill: {s}'
print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"Skill registry discovery failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_skill_loading_works(self):
        """Skills should load successfully via spec-based loading."""
        result = subprocess.run(
            ["uv", "run", "python", "-c", """
import sys
sys.path.insert(0, 'src')
from mcp.server.fastmcp import FastMCP
from agent.core.skill_registry import get_skill_registry

mcp = FastMCP('test')
registry = get_skill_registry()
success, msg = registry.load_skill('filesystem', mcp)
assert success, f'Failed to load filesystem: {msg}'
print('OK')
"""],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"Skill loading failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
