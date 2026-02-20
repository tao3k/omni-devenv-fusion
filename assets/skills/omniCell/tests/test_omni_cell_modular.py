import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="omniCell")
class TestOmniCellCommands:
    """Modular tests for omniCell skill."""

    async def test_execute_observe(self, skill_tester):
        """Test read-only execution (observe)."""
        result = await skill_tester.run("omniCell", "nuShell", command="ls", intent="observe")
        payload = result.data
        assert result.success
        assert isinstance(payload, dict)
        assert payload["status"] == "success"
        # Output structure depends on Nushell but should contain data
        assert "data" in payload

    async def test_execute_mutate(self, skill_tester, tmp_path, monkeypatch):
        """Test write execution (mutate)."""
        monkeypatch.chdir(tmp_path)

        # Write file using nu
        cmd = "echo 'hello' | save test.txt"
        result = await skill_tester.run("omniCell", "nuShell", command=cmd, intent="mutate")
        payload = result.data

        assert result.success
        assert payload["status"] == "success"
        assert (tmp_path / "test.txt").read_text().strip() == "hello"

    async def test_execute_missing_command(self, skill_tester):
        """Test error handling."""
        result = await skill_tester.run("omniCell", "nuShell", command="nonexistent_cmd_123")

        # It might succeed structurally but report error in data/status
        # Or fail if checking return code
        if result.success:
            payload = result.data
            assert payload["status"] == "error" or "not found" in str(payload)
        else:
            assert "error" in str(result.error).lower()

    async def test_chunked_start_and_batch(self, skill_tester):
        """Large outputs should support start/batch chunked delivery."""
        started = await skill_tester.run(
            "omniCell",
            "nuShell",
            command="0..300",
            chunked=True,
            batch_size=120,
        )
        started_payload = started.data
        assert started.success
        assert started_payload["status"] == "success"
        assert started_payload["action"] == "start"
        assert isinstance(started_payload["session_id"], str)
        assert started_payload["batch_count"] >= 1
        assert isinstance(started_payload["batch"], str)

        sid = started_payload["session_id"]
        batch0 = await skill_tester.run(
            "omniCell",
            "nuShell",
            action="batch",
            session_id=sid,
            batch_index=0,
        )
        batch_payload = batch0.data
        assert batch0.success
        assert batch_payload["status"] == "success"
        assert batch_payload["action"] == "batch"
        assert batch_payload["session_id"] == sid
        assert batch_payload["batch_index"] == 0
        assert isinstance(batch_payload["batch"], str)

    async def test_chunked_batch_requires_session_id(self, skill_tester):
        """action=batch must include a valid session_id."""
        result = await skill_tester.run(
            "omniCell",
            "nuShell",
            action="batch",
            batch_index=0,
        )
        payload = result.data
        assert result.success
        assert payload["status"] == "error"
        assert "session_id is required" in payload["message"]

    async def test_chunked_invalid_action(self, skill_tester):
        """Invalid chunked action should return standardized validation payload."""
        result = await skill_tester.run(
            "omniCell",
            "nuShell",
            action="invalid",
        )
        payload = result.data
        assert result.success
        assert payload["status"] == "error"
        assert payload["action"] == "invalid"
        assert payload["message"] == "action must be one of: batch, start"
