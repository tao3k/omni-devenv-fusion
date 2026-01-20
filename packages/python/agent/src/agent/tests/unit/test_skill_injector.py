"""
Unit tests for SkillInjector.

Tests skill injection with name boosting and hybrid search,
including the fix for accessing SkillContext attributes correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Import the actual classes/functions
from agent.core.omni.skill_injector import SkillInjector, get_skill_injector


# =============================================================================
# Mock SkillContext for testing
# =============================================================================


class MockSkillContext:
    """Mock SkillContext for testing SkillInjector."""

    def __init__(
        self,
        loaded_skills: Dict[str, Any] | None = None,
        core_skills: set | None = None,
    ) -> None:
        self.registry = MagicMock()
        self.registry.skills = loaded_skills or {}
        self._config = MagicMock()
        self._config.core_skills = core_skills or {"git", "writer", "runner"}
        self._jit = MagicMock()
        self._jit.try_load = AsyncMock()
        self._memory = MagicMock()
        self._memory.touch = MagicMock()


class MockVectorMemory:
    """Mock VectorMemory for testing."""

    def __init__(self) -> None:
        self._available = True

    async def search_tools_hybrid(
        self,
        query: str,
        limit: int = 5,
    ) -> list[Dict[str, Any]]:
        """Return mock search results."""
        return [
            {
                "id": "git.commit",
                "content": "Git commit tool",
                "metadata": {"skill_name": "git"},
                "distance": 0.1,
            }
        ]

    def get_all_skill_names(self) -> set:
        """Return mock skill names."""
        return {"git", "writer", "runner", "python", "file_ops"}


# =============================================================================
# SkillInjector Tests
# =============================================================================


class TestSkillInjectorInitialization:
    """Tests for SkillInjector initialization."""

    def test_init_creates_instance(self) -> None:
        """Verify injector initializes correctly."""
        injector = SkillInjector()
        assert injector._last_task == ""


class TestInjectForTask:
    """Tests for inject_for_task method."""

    @pytest.mark.asyncio
    async def test_inject_with_vector_memory_unavailable(self) -> None:
        """Verify graceful handling when vector memory unavailable."""
        injector = SkillInjector()

        with patch("agent.core.skill_runtime.context.get_skill_context") as mock_sc:
            mock_sc.return_value = MagicMock()
            with patch("agent.core.vector_store.get_vector_memory") as mock_vm:
                mock_vm.return_value = None

                # Should not raise
                await injector.inject_for_task("test task")

    @pytest.mark.asyncio
    async def test_inject_handles_error_gracefully(self) -> None:
        """Verify injector handles errors without crashing."""
        injector = SkillInjector()

        with patch("agent.core.skill_runtime.context.get_skill_context") as mock_sc:
            mock_sc.side_effect = Exception("Test error")
            with patch("agent.core.vector_store.get_vector_memory") as mock_vm:
                mock_vm.return_value = MagicMock()

                # Should not raise
                await injector.inject_for_task("test task")


class TestGetInjectedSkills:
    """Tests for get_injected_skills method."""

    def test_returns_empty_set_by_default(self) -> None:
        """Verify returns empty set before any injection."""
        injector = SkillInjector()
        skills = injector.get_injected_skills()
        assert skills == set()


class TestGetSkillInjector:
    """Tests for singleton getter."""

    def test_returns_singleton(self) -> None:
        """Verify singleton pattern works."""
        import agent.core.omni.skill_injector as module

        module._skill_injector = None

        injector1 = get_skill_injector()
        injector2 = get_skill_injector()

        assert injector1 is injector2


# =============================================================================
# SkillContext Attribute Access Tests (Regression Tests)
# =============================================================================


class TestSkillContextAttributeAccess:
    """Tests verifying correct SkillContext attribute access."""

    def test_skill_context_has_registry_skills(self) -> None:
        """Verify SkillContext uses registry.skills, not _skills."""
        from agent.core.skill_runtime.context import SkillContext

        # Verify the attribute exists
        assert hasattr(SkillContext, "__slots__")
        slots = SkillContext.__slots__
        assert "registry" in slots
        assert "_skills" not in slots

    def test_skill_context_has_config_core_skills(self) -> None:
        """Verify SkillContext uses _config.core_skills, not _core_skills."""
        from agent.core.skill_runtime.context import SkillContext

        slots = SkillContext.__slots__
        assert "_config" in slots
        assert "_core_skills" not in slots

    def test_skill_context_has_jit_loader(self) -> None:
        """Verify SkillContext uses _jit, not _try_jit_load."""
        from agent.core.skill_runtime.context import SkillContext

        slots = SkillContext.__slots__
        assert "_jit" in slots
        assert "_try_jit_load" not in slots

    def test_skill_context_has_memory_manager(self) -> None:
        """Verify SkillContext has _memory for TTL management."""
        from agent.core.skill_runtime.context import SkillContext

        slots = SkillContext.__slots__
        assert "_memory" in slots
