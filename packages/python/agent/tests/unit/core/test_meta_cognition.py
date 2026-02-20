"""Tests for Meta-Cognition Protocol components.

Tests for:
- PromptLoader: Loading prompts from assets/prompts/
- RoutingGuidanceProvider: Context provider for routing protocol
- create_omni_loop_context: Orchestrator factory for Omni Loop
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPromptLoader:
    """Test PromptLoader for loading prompts from assets/prompts/."""

    def test_load_intent_protocol_exists(self):
        """Test that intent_protocol.md can be loaded."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)
        assert content is not None
        assert len(content) > 0
        assert "<routing_protocol>" in content

    def test_load_nonexistent_prompt_returns_empty(self):
        """Test that nonexistent prompts return empty string when must_exist=False."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("nonexistent/prompt", must_exist=False)
        assert content == ""

    def test_load_nonexistent_prompt_raises_error(self):
        """Test that nonexistent prompts raise FileNotFoundError when must_exist=True."""
        from omni.agent.core.common.prompts import PromptLoader

        with pytest.raises(FileNotFoundError):
            PromptLoader.load("nonexistent/prompt", must_exist=True)

    def test_load_with_md_extension(self):
        """Test that .md extension is handled correctly."""
        from omni.agent.core.common.prompts import PromptLoader

        # With .md extension
        content1 = PromptLoader.load("routing/intent_protocol.md", must_exist=False)
        # Without .md extension
        content2 = PromptLoader.load("routing/intent_protocol", must_exist=False)

        assert content1 == content2
        assert "<routing_protocol>" in content1

    def test_load_returns_cached_result(self):
        """Test that repeated loads return cached result."""
        from omni.agent.core.common.prompts import PromptLoader

        content1 = PromptLoader.load("routing/intent_protocol", must_exist=False)
        content2 = PromptLoader.load("routing/intent_protocol", must_exist=False)

        assert content1 == content2
        # Same object due to LRU cache
        assert content1 is content2

    def test_load_rendered_with_variables(self):
        """Test that load_rendered substitutes variables."""
        from omni.agent.core.common.prompts import PromptLoader

        # Create a simple test prompt with variable
        with patch.object(PromptLoader, "load", return_value="Hello {{name}}!") as mock_load:
            result = PromptLoader.load_rendered("test/prompt", {"name": "World"})
            assert result == "Hello World!"

    def test_clear_cache(self):
        """Test that clear_cache removes cached prompts."""
        from omni.agent.core.common.prompts import PromptLoader

        # Clear cache first to ensure clean state
        PromptLoader.clear_cache()

        # Load to cache
        PromptLoader.load("routing/intent_protocol", must_exist=False)
        info = PromptLoader.load.cache_info()

        # Cache should have entries
        assert info.currsize >= 1

        # Clear cache
        PromptLoader.clear_cache()

        # Cache should be empty
        assert PromptLoader.load.cache_info().currsize == 0

    def test_prompt_contains_thinking_schema(self):
        """Test that intent_protocol contains the required thinking schema."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)

        # Check for required elements
        assert "<thinking>" in content
        assert "Current Goal:" in content
        assert "Observation:" in content
        assert "Gap:" in content
        assert "Intent:" in content
        # Check for either Routing: or Tool Call: (both are valid)
        assert "Routing:" in content or "Tool Call:" in content

    def test_prompts_dir_uses_settings_relative_path(self, tmp_path, monkeypatch):
        """`prompts.dir` relative path should resolve from project root."""
        from omni.agent.core.common.prompts import PromptLoader

        PromptLoader.clear_cache()
        prompt_dir = tmp_path / "custom_prompts" / "routing"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "intent_protocol.md").write_text("<routing_protocol>ok</routing_protocol>")

        monkeypatch.setattr(
            "omni.agent.core.common.prompts.get_setting",
            lambda key, default=None: "custom_prompts" if key == "prompts.dir" else default,
        )
        monkeypatch.setattr(
            "omni.agent.core.common.prompts.get_config_paths",
            lambda: type("P", (), {"project_root": tmp_path})(),
        )

        content = PromptLoader.load("routing/intent_protocol", must_exist=True)
        assert "<routing_protocol>ok</routing_protocol>" in content

    def test_prompts_dir_uses_settings_absolute_path(self, tmp_path, monkeypatch):
        """`prompts.dir` absolute path should be used as-is."""
        from omni.agent.core.common.prompts import PromptLoader

        PromptLoader.clear_cache()
        prompt_dir = tmp_path / "abs_prompts" / "routing"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "intent_protocol.md").write_text("<routing_protocol>abs</routing_protocol>")

        monkeypatch.setattr(
            "omni.agent.core.common.prompts.get_setting",
            lambda key, default=None: str(tmp_path / "abs_prompts")
            if key == "prompts.dir"
            else default,
        )

        content = PromptLoader.load("routing/intent_protocol", must_exist=True)
        assert "<routing_protocol>abs</routing_protocol>" in content


class TestRoutingGuidanceProvider:
    """Test RoutingGuidanceProvider for meta-cognition protocol."""

    def test_provider_initialization(self):
        """Test that provider can be initialized."""
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        provider = RoutingGuidanceProvider()
        assert provider.prompt_name == "routing/intent_protocol"

    def test_provider_custom_prompt_name(self):
        """Test that provider accepts custom prompt name."""
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        provider = RoutingGuidanceProvider(prompt_name="custom/protocol")
        assert provider.prompt_name == "custom/protocol"

    def test_provider_provide_returns_context_result(self):
        """Test that provider.provide returns valid ContextResult."""
        import asyncio
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        provider = RoutingGuidanceProvider()

        # Mock state
        state = {"messages": []}

        # Run async provider
        result = asyncio.run(provider.provide(state, budget=10000))

        assert result is not None
        assert hasattr(result, "content")
        assert hasattr(result, "token_count")
        assert hasattr(result, "name")
        assert hasattr(result, "priority")
        assert result.name == "routing_protocol"
        assert result.priority == 5
        assert "<routing_protocol>" in result.content

    def test_provider_caches_content(self):
        """Test that provider caches loaded content."""
        import asyncio
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        provider = RoutingGuidanceProvider()

        state = {"messages": []}

        # First call
        result1 = asyncio.run(provider.provide(state, budget=10000))

        # Second call should use cached content
        result2 = asyncio.run(provider.provide(state, budget=10000))

        assert result1.content == result2.content
        assert provider._content is not None

    def test_provider_priority_is_high(self):
        """Test that routing protocol has high priority (low number = high priority)."""
        import asyncio
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        provider = RoutingGuidanceProvider()
        state = {"messages": []}

        result = asyncio.run(provider.provide(state, budget=10000))

        # Priority 5 is high (0 is highest for Persona)
        assert result.priority == 5
        assert result.priority < 10  # Should be in top tier


class TestCreateOmniLoopContext:
    """Test create_omni_loop_context orchestrator factory."""

    def test_create_omni_loop_context_returns_orchestrator(self):
        """Test that factory returns ContextOrchestrator."""
        from omni.core.context.orchestrator import (
            create_omni_loop_context,
            ContextOrchestrator,
        )

        orchestrator = create_omni_loop_context()
        assert isinstance(orchestrator, ContextOrchestrator)

    def test_orchestrator_has_three_providers(self):
        """Rust-authoritative mode should include 3 providers."""
        from omni.core.context.orchestrator import create_omni_loop_context

        orchestrator = create_omni_loop_context()
        assert len(orchestrator._providers) == 3

    def test_orchestrator_has_routing_provider(self):
        """Test that orchestrator includes RoutingGuidanceProvider."""
        from omni.core.context.orchestrator import create_omni_loop_context
        from omni.agent.core.context.providers import RoutingGuidanceProvider

        orchestrator = create_omni_loop_context()
        provider_types = [type(p) for p in orchestrator._providers]
        assert RoutingGuidanceProvider in provider_types

    def test_orchestrator_has_system_persona_provider(self):
        """Test that orchestrator includes SystemPersonaProvider."""
        from omni.core.context.orchestrator import create_omni_loop_context
        from omni.core.context.providers import SystemPersonaProvider

        orchestrator = create_omni_loop_context()
        provider_types = [type(p) for p in orchestrator._providers]
        assert SystemPersonaProvider in provider_types

    def test_orchestrator_has_tools_provider(self):
        """Test that orchestrator includes AvailableToolsProvider."""
        from omni.core.context.orchestrator import create_omni_loop_context
        from omni.core.context.providers import AvailableToolsProvider

        orchestrator = create_omni_loop_context()
        provider_types = [type(p) for p in orchestrator._providers]
        assert AvailableToolsProvider in provider_types

    def test_orchestrator_excludes_active_skill_provider(self):
        """Rust-authoritative mode should exclude ActiveSkillProvider."""
        from omni.core.context.orchestrator import create_omni_loop_context
        from omni.core.context.providers import ActiveSkillProvider

        orchestrator = create_omni_loop_context()
        provider_types = [type(p) for p in orchestrator._providers]
        assert ActiveSkillProvider not in provider_types

    def test_orchestrator_default_disables_python_injection(self):
        """Default OmniLoop context should not include Python skill/memory providers."""
        from omni.core.context.orchestrator import create_omni_loop_context
        from omni.core.context.providers import ActiveSkillProvider, EpisodicMemoryProvider

        orchestrator = create_omni_loop_context()
        provider_types = [type(p) for p in orchestrator._providers]
        assert ActiveSkillProvider not in provider_types
        assert EpisodicMemoryProvider not in provider_types

    def test_providers_sorted_by_priority(self):
        """Test that providers are sorted by priority."""
        from omni.core.context.orchestrator import create_omni_loop_context

        orchestrator = create_omni_loop_context()
        priorities = [getattr(p, "priority", 50) for p in orchestrator._providers]

        # Should be sorted (lower = higher priority)
        assert priorities == sorted(priorities)

    def test_build_context_returns_string(self):
        """Test that build_context returns a string."""
        import asyncio
        from omni.core.context.orchestrator import create_omni_loop_context

        orchestrator = create_omni_loop_context()
        state = {"messages": [], "session_id": "test"}

        result = asyncio.run(orchestrator.build_context(state))

        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_context_includes_routing_protocol(self):
        """Test that built context includes routing protocol."""
        import asyncio
        from omni.core.context.orchestrator import create_omni_loop_context

        orchestrator = create_omni_loop_context()
        state = {"messages": [], "session_id": "test"}

        result = asyncio.run(orchestrator.build_context(state))

        assert "<routing_protocol>" in result


class TestIntentProtocolContent:
    """Test the content of intent_protocol.md."""

    def test_protocol_has_thinking_schema(self):
        """Test that protocol contains thinking schema."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)

        # Check for thinking tag
        assert "<thinking>" in content or "thinking" in content.lower()

    def test_protocol_requires_intent_formulation(self):
        """Test that protocol requires intent formulation."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)

        # Check for intent-related keywords
        assert "intent" in content.lower() or "goal" in content.lower()

    def test_protocol_requires_routing_explanation(self):
        """Test that protocol requires routing explanation."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)

        # Check for routing/selection keywords
        assert "tool" in content.lower() or "routing" in content.lower()

    def test_protocol_has_rules(self):
        """Test that protocol has operational rules."""
        from omni.agent.core.common.prompts import PromptLoader

        content = PromptLoader.load("routing/intent_protocol", must_exist=False)

        # Check for rules section
        assert "rule" in content.lower() or "do not" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
