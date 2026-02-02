import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="skill")
class TestSkillModular:
    """Modular tests for skill management skill."""

    async def test_discover(self, skill_tester):
        """Test discover execution."""
        result = await skill_tester.run("skill", "discover", intent="commit changes")
        assert result.success
        assert result.output["status"] == "success"
        assert len(result.output["discovered_capabilities"]) > 0

    async def test_list_index(self, skill_tester):
        """Test list_index execution."""
        result = await skill_tester.run("skill", "list_index")
        assert result.success
        assert "Total skills" in result.output

    async def test_jit_install(self, skill_tester):
        """Test jit_install execution."""
        result = await skill_tester.run("skill", "jit_install", skill_id="test-skill")
        assert result.success
        assert "Installing skill: test-skill" in result.output
