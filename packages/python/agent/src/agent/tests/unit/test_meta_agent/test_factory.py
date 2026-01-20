"""test_factory.py - MetaAgent Factory Tests"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from agent.core.meta_agent import MetaAgent, GenerationResult


class TestMetaAgent:
    """Tests for MetaAgent class."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        client.complete = AsyncMock(return_value={"content": '{"skill_name": "test_skill"}'})
        return client

    @pytest.fixture
    def meta_agent(self, mock_llm_client):
        """Create a MetaAgent with mock LLM client."""
        return MetaAgent(llm_client=mock_llm_client)

    def test_initialization(self, meta_agent):
        """MetaAgent should initialize components."""
        assert hasattr(meta_agent, "prompt")
        assert hasattr(meta_agent, "validator")
        assert hasattr(meta_agent, "harvester")
        assert hasattr(meta_agent, "llm_client")

    def test_initialization_without_llm(self):
        """Should handle initialization without LLM client."""
        with patch("agent.core.meta_agent.factory.InferenceClient") as mock_client:
            mock_client.return_value = MagicMock()
            agent = MetaAgent(llm_client=None)
            assert agent.llm_client is not None

    def test_wrap_in_skill_script(self, meta_agent):
        """Should wrap implementation in skill script structure."""
        implementation = "return {'data': 'test'}"
        wrapped = meta_agent._wrap_in_skill_script("test_skill", implementation)

        assert "test_skill" in wrapped
        assert "@skill_command" in wrapped
        assert "async def test_skill" in wrapped
        assert implementation in wrapped

    def test_create_refinement_prompt(self, meta_agent):
        """Should create proper refinement prompt."""
        prompt = meta_agent._create_refinement_prompt(
            requirement="Parse CSV files",
            code="def parse(): pass",
            error="IndentationError",
        )

        assert "Parse CSV files" in prompt
        assert "IndentationError" in prompt
        assert "refined_code" in prompt


class TestMetaAgentGenerateSkill:
    """Tests for MetaAgent.generate_skill method."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_no_llm_client(self):
        """Should fail gracefully when no LLM client."""
        meta = MetaAgent(llm_client=None)
        result = await meta.generate_skill("Test requirement")

        assert result.success is False
        assert "No LLM client" in result.error

    @pytest.mark.asyncio
    async def test_skill_generation_success(self, mock_llm_client):
        """Should generate skill successfully."""
        # Mock responses for skill spec and test generation
        skill_response = '{"skill_name": "csv_parser", "commands": [{"name": "parse", "description": "Parse CSV", "parameters": [], "implementation": "return {}"}]}'
        test_response = '{"test_code": "import pytest"}'

        mock_llm_client.complete = AsyncMock(
            side_effect=[
                {"content": skill_response},
                {"content": test_response},
            ]
        )

        meta = MetaAgent(llm_client=mock_llm_client)
        result = await meta.generate_skill("I need a CSV parser")

        assert result.success is True
        assert result.skill_name == "csv_parser"

    @pytest.mark.asyncio
    async def test_skill_generation_no_commands(self, mock_llm_client):
        """Should fail when no commands in response."""
        mock_llm_client.complete = AsyncMock(
            return_value={"content": '{"skill_name": "empty_skill"}'}
        )

        meta = MetaAgent(llm_client=mock_llm_client)
        result = await meta.generate_skill("I need a skill")

        assert result.success is False
        assert "No commands" in result.error

    @pytest.mark.asyncio
    async def test_skill_generation_json_error(self, mock_llm_client):
        """Should handle invalid JSON from LLM."""
        mock_llm_client.complete = AsyncMock(return_value={"content": "not valid json"})

        meta = MetaAgent(llm_client=mock_llm_client)
        result = await meta.generate_skill("I need a skill")

        assert result.success is False
        assert "JSON" in result.error


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_generate_skill_function(self):
        """generate_skill convenience function should work."""
        from agent.core.meta_agent import generate_skill

        with patch("agent.core.meta_agent.factory.MetaAgent") as MockMetaAgent:
            mock_agent = AsyncMock()
            mock_agent.generate_skill = AsyncMock(
                return_value=GenerationResult(
                    success=True,
                    skill_name="test",
                )
            )
            MockMetaAgent.return_value = mock_agent

            result = await generate_skill("Test requirement")
            MockMetaAgent.assert_called_once()

    @pytest.mark.asyncio
    async def test_harvest_skills_function(self):
        """harvest_skills convenience function should work."""
        from agent.core.meta_agent import harvest_skills

        with patch("agent.core.meta_agent.factory.MetaAgent") as MockMetaAgent:
            mock_agent = AsyncMock()
            mock_agent.harvest_and_suggest = AsyncMock(return_value=[])
            MockMetaAgent.return_value = mock_agent

            result = await harvest_skills(min_frequency=2)
            MockMetaAgent.assert_called_once()
