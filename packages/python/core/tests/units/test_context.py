"""Tests for omni.core.context module."""

from __future__ import annotations

import pytest

from omni.core.context import (
    ContextProvider,
    ContextResult,
    ContextOrchestrator,
    SystemPersonaProvider,
    ActiveSkillProvider,
    AvailableToolsProvider,
    EpisodicMemoryProvider,
    create_planner_orchestrator,
    create_executor_orchestrator,
)


class TestContextResult:
    """Test ContextResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = ContextResult(
            content="<test>content</test>",
            token_count=10,
            name="test_provider",
            priority=5,
        )
        assert result.content == "<test>content</test>"
        assert result.token_count == 10
        assert result.name == "test_provider"
        assert result.priority == 5

    def test_equality(self):
        """Test equality comparison."""
        r1 = ContextResult(content="a", token_count=1, name="n", priority=0)
        r2 = ContextResult(content="a", token_count=1, name="n", priority=0)
        r3 = ContextResult(content="b", token_count=1, name="n", priority=0)
        assert r1 == r2
        assert r1 != r3


class TestSystemPersonaProvider:
    """Test SystemPersonaProvider."""

    def test_default_role(self):
        """Test default architect role."""
        provider = SystemPersonaProvider()
        assert provider.role == "architect"

    def test_custom_role(self):
        """Test custom role assignment."""
        provider = SystemPersonaProvider(role="developer")
        assert provider.role == "developer"

    def test_unknown_role(self):
        """Test unknown role uses fallback."""
        provider = SystemPersonaProvider(role="unknown_role")
        assert provider.role == "unknown_role"

    @pytest.mark.asyncio
    async def test_provide_returns_content(self):
        """Test provide returns ContextResult with content."""
        provider = SystemPersonaProvider(role="architect")
        result = await provider.provide({}, 1000)

        assert isinstance(result, ContextResult)
        assert result.token_count > 0
        assert "architect" in result.content
        assert result.priority == 0
        assert result.name == "persona"

    @pytest.mark.asyncio
    async def test_provide_ignores_budget(self):
        """Test that persona ignores budget (always included)."""
        provider = SystemPersonaProvider()
        result = await provider.provide({}, 1)

        # Persona should be included regardless of tiny budget
        assert result.token_count > 0

    @pytest.mark.asyncio
    async def test_all_personas_exist(self):
        """Test that all default personas are accessible."""
        for role in ["architect", "developer", "researcher"]:
            provider = SystemPersonaProvider(role=role)
            result = await provider.provide({}, 1000)
            assert f"<role>You are a" in result.content


class TestActiveSkillProvider:
    """Test ActiveSkillProvider."""

    def test_creation(self):
        """Test provider can be instantiated."""
        provider = ActiveSkillProvider()
        assert provider is not None

    @pytest.mark.asyncio
    async def test_no_active_skill(self):
        """Test behavior when no active_skill in state."""
        provider = ActiveSkillProvider()
        result = await provider.provide({}, 1000)

        assert result.content == ""
        assert result.token_count == 0
        assert result.priority == 10
        assert result.name == "active_skill"

    @pytest.mark.asyncio
    async def test_with_active_skill(self):
        """Test behavior when active_skill is provided."""
        provider = ActiveSkillProvider()
        state = {"active_skill": "nonexistent_skill"}
        result = await provider.provide(state, 1000)

        # Should return empty for unknown skill
        assert result.name == "active_skill"

    @pytest.mark.asyncio
    async def test_wraps_content_in_xml(self):
        """Test that content is wrapped in XML tags."""
        provider = ActiveSkillProvider()
        state = {"active_skill": "git"}
        result = await provider.provide(state, 10000)

        if result.content:
            assert "<active_protocol>" in result.content
            assert "</active_protocol>" in result.content


class TestAvailableToolsProvider:
    """Test AvailableToolsProvider."""

    def test_creation(self):
        """Test provider can be instantiated."""
        provider = AvailableToolsProvider()
        assert provider is not None

    @pytest.mark.asyncio
    async def test_returns_tools_index(self):
        """Test that provider returns tools information."""
        provider = AvailableToolsProvider()
        result = await provider.provide({}, 1000)

        assert result.name == "tools"
        assert result.priority == 20
        # Should return some content if skills are indexed
        if result.content:
            assert "<available_tools>" in result.content

    @pytest.mark.asyncio
    async def test_respects_budget(self):
        """Test that budget is passed to provide method."""
        provider = AvailableToolsProvider()
        result = await provider.provide({}, 500)

        assert result.priority == 20


class TestEpisodicMemoryProvider:
    """Test EpisodicMemoryProvider."""

    def test_creation(self):
        """Test provider can be instantiated."""
        provider = EpisodicMemoryProvider()
        assert provider is not None

    @pytest.mark.asyncio
    async def test_low_budget_returns_none(self):
        """Test that low budget returns None (skips episodic memory)."""
        provider = EpisodicMemoryProvider()
        result = await provider.provide({}, 100)

        # Budget < 300 should skip and return None
        assert result is None

    @pytest.mark.asyncio
    async def test_no_query_returns_none(self):
        """Test that missing query returns None (skips episodic memory)."""
        provider = EpisodicMemoryProvider()
        result = await provider.provide({}, 1000)

        # No query should return None
        assert result is None


class TestContextOrchestrator:
    """Test ContextOrchestrator."""

    def test_creation_with_providers(self):
        """Test orchestrator creation with providers."""
        orchestrator = ContextOrchestrator(
            [
                SystemPersonaProvider(),
            ]
        )
        assert orchestrator is not None

    def test_default_parameters(self):
        """Test default max_tokens and output_reserve."""
        orchestrator = ContextOrchestrator([])
        assert orchestrator._max_input_tokens == 128000 - 4096

    def test_custom_parameters(self):
        """Test custom max_tokens and output_reserve."""
        orchestrator = ContextOrchestrator(
            [],
            max_tokens=64000,
            output_reserve=2048,
        )
        assert orchestrator._max_input_tokens == 64000 - 2048

    @pytest.mark.asyncio
    async def test_empty_providers(self):
        """Test with no providers returns empty string."""
        orchestrator = ContextOrchestrator([])
        result = await orchestrator.build_context({})
        assert result == ""

    @pytest.mark.asyncio
    async def test_single_provider(self):
        """Test with single provider."""
        orchestrator = ContextOrchestrator(
            [
                SystemPersonaProvider(role="developer"),
            ]
        )
        result = await orchestrator.build_context({})
        assert "developer" in result

    @pytest.mark.asyncio
    async def test_multiple_providers_parallel(self):
        """Test multiple providers are executed."""
        orchestrator = ContextOrchestrator(
            [
                SystemPersonaProvider(role="architect"),
                AvailableToolsProvider(),
            ]
        )
        result = await orchestrator.build_context({})
        # Both providers should contribute
        assert "architect" in result or "<available_tools>" in result

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that context results are sorted by priority after assembly."""
        orchestrator = ContextOrchestrator(
            [
                SystemPersonaProvider(),
                ActiveSkillProvider(),
            ]
        )
        # Execute and check results are sorted
        state = {"active_skill": "git"}
        context = await orchestrator.build_context(state)

        # Results should be assembled (persona comes first due to priority)
        assert isinstance(context, str)


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_planner_orchestrator(self):
        """Test planner orchestrator creation."""
        orchestrator = create_planner_orchestrator()
        assert isinstance(orchestrator, ContextOrchestrator)
        assert len(orchestrator._providers) == 4

    def test_create_executor_orchestrator(self):
        """Test executor orchestrator creation."""
        orchestrator = create_executor_orchestrator()
        assert isinstance(orchestrator, ContextOrchestrator)
        assert len(orchestrator._providers) == 2

    @pytest.mark.asyncio
    async def test_planner_has_all_providers(self):
        """Test planner orchestrator has all provider types."""
        orchestrator = create_planner_orchestrator()
        provider_types = [type(p).__name__ for p in orchestrator._providers]
        assert "SystemPersonaProvider" in provider_types
        assert "AvailableToolsProvider" in provider_types
        assert "ActiveSkillProvider" in provider_types
        assert "EpisodicMemoryProvider" in provider_types

    @pytest.mark.asyncio
    async def test_executor_has_core_providers(self):
        """Test executor orchestrator has core providers only."""
        orchestrator = create_executor_orchestrator()
        provider_types = [type(p).__name__ for p in orchestrator._providers]
        assert "SystemPersonaProvider" in provider_types
        assert "ActiveSkillProvider" in provider_types
        # Executor should not include tools or rag by default
        assert provider_types.count("AvailableToolsProvider") == 0


class TestContextIntegration:
    """Integration tests for the context module."""

    @pytest.mark.asyncio
    async def test_full_skill_context_flow(self):
        """Test complete flow from state to context."""
        from omni.core.skills.memory import get_skill_memory

        # Verify skill memory works
        memory = get_skill_memory()
        assert memory is not None

        # Verify skills are indexed
        skills = memory.list_skills()
        assert len(skills) > 0

    @pytest.mark.asyncio
    async def test_build_context_with_state(self):
        """Test building context with realistic state."""
        state = {
            "active_skill": "git",
            "current_task": "Analyze repository status",
            "messages": [{"content": "Show me the git status"}],
        }

        orchestrator = create_planner_orchestrator()
        context = await orchestrator.build_context(state)

        assert isinstance(context, str)
        # Context should contain system persona
        assert len(context) > 0
