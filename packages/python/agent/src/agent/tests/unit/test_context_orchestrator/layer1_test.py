"""
Unit tests for Layer 1: System Persona.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestLayer1SystemPersona:
    """Tests for Layer 1: System Persona."""

    def test_layer_priority(self) -> None:
        """Verify layer has correct priority."""
        from agent.core.context_orchestrator import Layer1_SystemPersona

        assert Layer1_SystemPersona.priority == 1
        assert Layer1_SystemPersona.name == "system_persona"

    @pytest.mark.asyncio
    async def test_assemble_with_context_file(self) -> None:
        """Verify layer assembles context from file."""
        from agent.core.context_orchestrator import Layer1_SystemPersona

        layer = Layer1_SystemPersona()
        with patch(
            "agent.core.context_orchestrator.layers.layer1_persona.get_project_root"
        ) as mock_root:
            mock_root.return_value = Path("/test")
            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.return_value = "<system_context><role>Test</role></system_context>"

                content, tokens = await layer.assemble("test task", [], 10000)

                assert "<system_context>" in content
                assert tokens > 0

    @pytest.mark.asyncio
    async def test_assemble_without_context_file(self) -> None:
        """Verify layer uses fallback when file missing."""
        from agent.core.context_orchestrator import Layer1_SystemPersona

        layer = Layer1_SystemPersona()
        # Use a path that doesn't exist
        with patch(
            "agent.core.context_orchestrator.layers.layer1_persona.get_project_root"
        ) as mock_root:
            mock_root.return_value = Path("/nonexistent_path_12345")

            content, tokens = await layer.assemble("test task", [], 10000)

            assert "<system_context>" in content

    @pytest.mark.asyncio
    async def test_assemble_with_empty_task(self) -> None:
        """Verify layer handles empty task."""
        from agent.core.context_orchestrator import Layer1_SystemPersona

        layer = Layer1_SystemPersona()
        content, tokens = await layer.assemble("", [], 10000)

        assert "<system_context>" in content
