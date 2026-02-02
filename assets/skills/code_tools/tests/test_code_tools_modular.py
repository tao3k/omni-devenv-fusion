import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestCodeToolsModular:
    """Modular tests for code_tools skill."""

    async def test_smart_ast_search_functions(self, skill_tester):
        """Test smart_ast_search execution for functions."""
        result = await skill_tester.run(
            "code_tools", "smart_ast_search", query="functions", limit=5
        )
        assert result.success
        assert result.output["tool"] == "ast-grep"
        assert isinstance(result.output["matches"], list)

    async def test_smart_ast_search_classes(self, skill_tester):
        """Test smart_ast_search execution for classes."""
        result = await skill_tester.run("code_tools", "smart_ast_search", query="classes", limit=5)
        assert result.success
        assert result.output["tool"] == "ast-grep"

    async def test_smart_ast_search_custom_pattern(self, skill_tester):
        """Test smart_ast_search execution with custom pattern."""
        result = await skill_tester.run(
            "code_tools", "smart_ast_search", pattern="import $MOD", limit=5
        )
        assert result.success
        assert result.output["tool"] == "ast-grep"
