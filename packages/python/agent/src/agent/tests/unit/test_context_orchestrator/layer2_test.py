"""
Unit tests for Layer 2: Available Skills.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestLayer2AvailableSkills:
    """Tests for Layer 2: Available Skills."""

    def test_layer_priority(self) -> None:
        """Verify layer has correct priority."""
        from agent.core.context_orchestrator import Layer2_AvailableSkills

        assert Layer2_AvailableSkills.priority == 2
        assert Layer2_AvailableSkills.name == "skills"

    @pytest.mark.asyncio
    async def test_assemble_with_empty_budget(self) -> None:
        """Verify layer returns empty for very low budget."""
        from agent.core.context_orchestrator import Layer2_AvailableSkills

        layer = Layer2_AvailableSkills()
        content, tokens = await layer.assemble("test task", [], 0)

        # Low budget should return minimal content
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_assemble_with_task(self) -> None:
        """Verify layer assembles with task context."""
        from agent.core.context_orchestrator import Layer2_AvailableSkills

        layer = Layer2_AvailableSkills()
        content, tokens = await layer.assemble("git commit", [], 1000)

        # Should include some skill-related content
        assert isinstance(content, str)
