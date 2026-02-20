"""Response-shape adapter tests for omniCell nuShell command."""

from __future__ import annotations

import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="omniCell")
class TestOmniCellResponseAdapter:
    async def test_nu_shell_empty_command_returns_status_error(self, skill_tester) -> None:
        result = await skill_tester.run("omniCell", "nuShell", command="")

        assert result.success
        payload = result.data
        assert payload["status"] == "error"
        assert payload["message"] == "command is required"
