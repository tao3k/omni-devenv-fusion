"""Modular tests for skill management skill.

Use result.data for the unwrapped payload (dict or parsed JSON) and result.text
for string assertions, so tests pass whether output is raw or MCP content envelope.
"""

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
        data = result.data
        assert isinstance(data, dict), "discover returns a dict"
        assert data.get("status") == "success"
        capabilities = data.get("discovered_capabilities", [])
        assert len(capabilities) > 0
        first = capabilities[0]
        for field in (
            "tool",
            "usage",
            "score",
            "final_score",
            "confidence",
            "ranking_reason",
            "input_schema_digest",
        ):
            assert field in first

    async def test_list_index(self, skill_tester):
        """Test list_index execution."""
        result = await skill_tester.run("skill", "list_index")
        assert result.success
        assert "Total skills" in result.text

    async def test_jit_install(self, skill_tester):
        """Test jit_install execution."""
        result = await skill_tester.run("skill", "jit_install", skill_id="test-skill")
        assert result.success
        assert "Installing skill: test-skill" in result.text
