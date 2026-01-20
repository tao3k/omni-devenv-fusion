"""
Integration test for MCP server lifespan.

Tests that:
1. SkillContext has the required observer methods (subscribe, etc.)
2. All key imports for MCP server initialization work
3. The full lifespan initialization path is valid

Usage:
    uv run pytest packages/python/agent/src/agent/tests/integration/test_mcp_lifespan.py -v
"""

import pytest


class TestMCPServerImports:
    """Test all imports required for MCP server initialization."""

    def test_mcp_server_lifespan_import(self):
        """Verify lifespan module imports correctly."""
        from agent.mcp_server.lifespan import server_lifespan

        assert callable(server_lifespan)

    def test_skill_runtime_import(self):
        """Verify skill_runtime module imports correctly."""
        from agent.core.skill_runtime import get_skill_context, SkillContext

        assert callable(get_skill_context)
        assert SkillContext is not None

    def test_skill_context_observer_mixin_import(self):
        """Verify ObserverMixin is properly inherited."""
        from agent.core.skill_runtime import SkillContext

        assert hasattr(SkillContext, "subscribe")

    def test_watcher_import(self):
        """Verify watcher module imports correctly."""
        from agent.core.skill_runtime.support.watcher import start_global_watcher

        assert callable(start_global_watcher)

    def test_vector_store_import(self):
        """Verify vector_store module imports correctly."""
        from agent.core.vector_store import get_vector_memory

        assert callable(get_vector_memory)

    def test_all_lifespan_dependencies(self):
        """Verify all dependencies can be imported together."""
        # These are imported in the lifespan context
        from agent.core.skill_runtime import get_skill_context
        from agent.core.skill_runtime.support.watcher import start_global_watcher

        # Should not raise any import errors
        ctx = get_skill_context()
        assert ctx is not None


class TestMCPServerLifespan:
    """Test MCP server lifespan initialization."""

    def test_skill_context_has_subscribe_method(self):
        """Verify SkillContext has subscribe method from ObserverMixin."""
        from agent.core.skill_runtime import SkillContext, get_skill_context

        # Verify the method exists on the class
        assert hasattr(SkillContext, "subscribe"), "SkillContext should have subscribe method"

        # Verify we can create an instance and call subscribe
        ctx = get_skill_context()
        assert callable(getattr(ctx, "subscribe", None)), "subscribe should be callable"

    def test_skill_context_has_notify_change_method(self):
        """Verify SkillContext has _notify_change method from ObserverMixin."""
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        assert callable(getattr(ctx, "_notify_change", None)), "_notify_change should be callable"

    def test_skill_context_has_fire_and_forget_method(self):
        """Verify SkillContext has _fire_and_forget method from ObserverMixin."""
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        assert callable(getattr(ctx, "_fire_and_forget", None)), (
            "_fire_and_forget should be callable"
        )

    def test_skill_context_observers_initialized(self):
        """Verify SkillContext initializes _observers list."""
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        assert hasattr(ctx, "_observers"), "SkillContext should have _observers attribute"
        assert isinstance(ctx._observers, list), "_observers should be a list"

    def test_subscribe_receives_callback(self):
        """Verify subscribe actually adds callbacks to the observers list."""
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        initial_count = len(ctx._observers)

        # Define a test callback
        def test_callback(changes):
            pass

        ctx.subscribe(test_callback)

        assert len(ctx._observers) == initial_count + 1
        assert test_callback in ctx._observers

    def test_subscribe_prevents_duplicates(self):
        """Verify subscribing the same callback twice doesn't create duplicates."""
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        # Clear observers for this test
        ctx._observers.clear()

        def test_callback(changes):
            pass

        ctx.subscribe(test_callback)
        ctx.subscribe(test_callback)  # Should be ignored

        assert len(ctx._observers) == 1, "Duplicate subscriptions should be prevented"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
