import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="omniCell")
class TestOmniCellCommands:
    """Modular tests for omniCell skill."""

    async def test_execute_observe(self, skill_tester):
        """Test read-only execution (observe)."""
        result = await skill_tester.run("omniCell", "execute", command="ls", intent="observe")
        assert result.success
        assert isinstance(result.output, dict)
        assert result.output["status"] == "success"
        # Output structure depends on Nushell but should contain data
        assert "data" in result.output

    async def test_execute_mutate(self, skill_tester, tmp_path, monkeypatch):
        """Test write execution (mutate)."""
        monkeypatch.chdir(tmp_path)

        # Write file using nu
        cmd = "echo 'hello' | save test.txt"
        result = await skill_tester.run("omniCell", "execute", command=cmd, intent="mutate")

        assert result.success
        assert result.output["status"] == "success"
        assert (tmp_path / "test.txt").read_text().strip() == "hello"

    async def test_execute_missing_command(self, skill_tester):
        """Test error handling."""
        result = await skill_tester.run("omniCell", "execute", command="nonexistent_cmd_123")

        # It might succeed structurally but report error in data/status
        # Or fail if checking return code
        if result.success:
            assert result.output["status"] == "error" or "not found" in str(result.output)
        else:
            assert "error" in str(result.error).lower()
