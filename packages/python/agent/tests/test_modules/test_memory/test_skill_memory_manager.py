"""
Tests for skill_runtime.core.memory_core.SkillMemoryManager.

Tests LRU eviction and TTL functionality.
"""

import pytest
import time
from unittest.mock import MagicMock


class TestSkillMemoryManager:
    """Unit tests for SkillMemoryManager LRU and TTL functionality."""

    def _create_manager(
        self,
        core_skills: set[str] | None = None,
        ttl_seconds: float = 300.0,
        ttl_check_interval: float = 60.0,
        max_loaded_skills: int = 10,
    ) -> tuple:
        """Create a SkillMemoryManager instance with mocks."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        if core_skills is None:
            core_skills = {"core_skill"}

        manager = SkillMemoryManager(
            core_skills=core_skills,
            ttl_seconds=ttl_seconds,
            ttl_check_interval=ttl_check_interval,
            max_loaded_skills=max_loaded_skills,
        )

        # Mock unload callback
        unload_skill = MagicMock(return_value=True)

        return manager, unload_skill

    # =========================================================================
    # LRU Tracking Tests
    # =========================================================================

    def test_touch_updates_timestamp_and_order(self):
        """Test that touch updates timestamp and LRU order."""
        manager, _ = self._create_manager()

        manager.touch("skill_a")
        manager.touch("skill_b")
        manager.touch("skill_c")

        # All skills should have timestamps
        assert "skill_a" in manager.lru_timestamps
        assert "skill_b" in manager.lru_timestamps
        assert "skill_c" in manager.lru_timestamps

        # LRU order should reflect last touch
        assert manager.lru_order[-1] == "skill_c"

    def test_touch_moves_skill_to_end_of_lru(self):
        """Test that touching a skill moves it to the end of LRU order."""
        manager, _ = self._create_manager()

        manager.touch("skill_a")
        manager.touch("skill_b")
        manager.touch("skill_a")  # Re-touch skill_a

        # skill_a should now be last
        assert manager.lru_order[-1] == "skill_a"
        assert manager.lru_order[-2] == "skill_b"

    def test_lru_order_property(self):
        """Test LRU order property returns correct list."""
        manager, _ = self._create_manager()

        manager.touch("skill_1")
        manager.touch("skill_2")

        order = manager.lru_order
        assert order == ["skill_1", "skill_2"]

    def test_lru_timestamps_property(self):
        """Test LRU timestamps property returns correct dict."""
        manager, _ = self._create_manager()

        manager.touch("skill_x")
        timestamps = manager.lru_timestamps

        assert "skill_x" in timestamps
        assert isinstance(timestamps["skill_x"], float)

    # =========================================================================
    # TTL Check Tests
    # =========================================================================

    def test_core_skills_never_expire(self):
        """Test that core skills never expire regardless of TTL."""
        manager, _ = self._create_manager(
            core_skills={"always_core"},
            ttl_seconds=0.001,  # Very short TTL
        )

        manager.touch("always_core")

        # Even after TTL expires, core skills should not be expired
        time.sleep(0.01)
        assert manager.is_ttl_expired("always_core") is False

    def test_skill_expires_after_ttl(self):
        """Test that non-core skills expire after TTL."""
        manager, _ = self._create_manager(
            core_skills=set(),
            ttl_seconds=0.01,  # 10ms TTL
        )

        manager.touch("transient_skill")

        # Before TTL - not expired
        assert manager.is_ttl_expired("transient_skill") is False

        # After TTL - expired
        time.sleep(0.02)
        assert manager.is_ttl_expired("transient_skill") is True

    def test_skill_without_timestamp_is_expired(self):
        """Test that skills without timestamps are considered expired."""
        manager, _ = self._create_manager()

        # Skill was never touched
        assert manager.is_ttl_expired("never_touched") is True

    def test_ttl_properties(self):
        """Test TTL properties return correct values."""
        manager, _ = self._create_manager(
            ttl_seconds=600.0,
            ttl_check_interval=120.0,
        )

        assert manager.ttl_seconds == 600.0
        assert manager.ttl_check_interval == 120.0

    # =========================================================================
    # Memory Limit Enforcement Tests
    # =========================================================================

    def test_enforce_memory_limit_under_capacity(self):
        """Test that no skills are unloaded when under limit."""
        manager, unload_skill = self._create_manager(
            max_loaded_skills=10,
        )

        loaded_skills = {
            "skill_1": MagicMock(),
            "skill_2": MagicMock(),
            "skill_3": MagicMock(),
        }
        pinned_skills = set()

        for name in loaded_skills:
            manager.touch(name)

        result = manager.enforce_memory_limit(loaded_skills, pinned_skills, unload_skill)

        assert result == 0
        unload_skill.assert_not_called()

    def test_enforce_memory_limit_evicts_oldest_lru(self):
        """Test that oldest LRU skills are evicted first."""
        manager, unload_skill = self._create_manager(
            max_loaded_skills=2,
        )

        loaded_skills = {
            "skill_oldest": MagicMock(),
            "skill_middle": MagicMock(),
            "skill_newest": MagicMock(),
        }
        pinned_skills = set()

        # Touch in order: oldest -> middle -> newest
        manager.touch("skill_oldest")
        time.sleep(0.001)
        manager.touch("skill_middle")
        time.sleep(0.001)
        manager.touch("skill_newest")

        result = manager.enforce_memory_limit(loaded_skills, pinned_skills, unload_skill)

        # Should evict 1 skill (3 loaded - 2 limit)
        assert result == 1
        # skill_oldest should be evicted (it's LRU)
        assert unload_skill.call_count == 1
        unload_skill.assert_called_with("skill_oldest")

    def test_enforce_memory_limit_respects_pinned(self):
        """Test that pinned/core skills are not evicted."""
        manager, unload_skill = self._create_manager(
            max_loaded_skills=2,
            core_skills={"pinned_skill"},
        )

        loaded_skills = {
            "pinned_skill": MagicMock(),  # Core skill
            "skill_2": MagicMock(),
            "skill_3": MagicMock(),
        }
        pinned_skills = {"pinned_skill"}

        manager.touch("pinned_skill")
        manager.touch("skill_2")
        manager.touch("skill_3")

        result = manager.enforce_memory_limit(loaded_skills, pinned_skills, unload_skill)

        # Should evict 1 skill, but not pinned_skill
        assert result == 1
        # skill_2 should be evicted (it's LRU among non-pinned)
        unload_skill.assert_called_with("skill_2")

    def test_enforce_memory_limit_evicts_expired_first(self):
        """Test that TTL-expired skills are evicted before LRU."""
        manager, unload_skill = self._create_manager(
            max_loaded_skills=10,
            ttl_seconds=0.01,  # Short TTL
        )

        loaded_skills = {
            "expired_skill": MagicMock(),
            "active_skill": MagicMock(),
        }
        pinned_skills = set()

        # Touch both skills
        manager.touch("expired_skill")
        manager.touch("active_skill")

        # Wait for TTL to expire on expired_skill
        time.sleep(0.02)

        # Add more skills to exceed limit
        for i in range(10):
            loaded_skills[f"extra_{i}"] = MagicMock()
            manager.touch(f"extra_{i}")

        # Reset mock to track only expired_skill
        unload_skill.reset_mock()

        result = manager.enforce_memory_limit(loaded_skills, pinned_skills, unload_skill)

        # expired_skill should be evicted first (TTL expiration)
        assert unload_skill.call_count >= 1
        calls = [call[0][0] for call in unload_skill.call_args_list]
        assert "expired_skill" in calls

    # =========================================================================
    # TTL Cleanup Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cleanup_expired_skills_removes_expired(self):
        """Test that cleanup removes TTL-expired skills."""
        manager, unload_skill = self._create_manager(
            ttl_seconds=0.01,
            ttl_check_interval=0.0,  # No interval restriction
        )

        loaded_skills = {
            "expired_skill": MagicMock(),
        }

        manager.touch("expired_skill")

        # Wait for TTL to expire
        time.sleep(0.02)

        result = await manager.cleanup_expired_skills(loaded_skills, unload_skill)

        assert result == 1
        unload_skill.assert_called_once_with("expired_skill")

    @pytest.mark.asyncio
    async def test_cleanup_expired_skills_respects_interval(self):
        """Test that cleanup respects check interval."""
        manager, unload_skill = self._create_manager(
            ttl_seconds=0.01,
            ttl_check_interval=60.0,  # Long interval
        )

        loaded_skills = {"skill": MagicMock()}
        manager.touch("skill")

        # Wait for TTL
        time.sleep(0.02)

        # First cleanup - should run
        await manager.cleanup_expired_skills(loaded_skills, unload_skill)

        # Reset and run again immediately - should skip
        unload_skill.reset_mock()
        await manager.cleanup_expired_skills(loaded_skills, unload_skill)

        # Should skip due to interval
        assert unload_skill.call_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_skills_preserves_active(self):
        """Test that cleanup preserves non-expired skills."""
        manager, unload_skill = self._create_manager(
            ttl_seconds=0.01,
            ttl_check_interval=0.0,
        )

        loaded_skills = {
            "active_skill": MagicMock(),
        }
        manager.touch("active_skill")

        # Don't wait - skill should still be active
        result = await manager.cleanup_expired_skills(loaded_skills, unload_skill)

        assert result == 0
        unload_skill.assert_not_called()

    def test_last_ttl_check_property(self):
        """Test last_ttl_check property getter and setter."""
        manager, _ = self._create_manager()

        initial_value = manager.last_ttl_check

        # Set new value
        new_value = 12345.678
        manager.last_ttl_check = new_value

        assert manager.last_ttl_check == new_value
        assert manager.last_ttl_check != initial_value

    def test_max_loaded_skills_property(self):
        """Test max_loaded_skills property returns correct value."""
        manager, _ = self._create_manager(max_loaded_skills=25)

        assert manager.max_loaded_skills == 25


class TestSkillMemoryManagerEdgeCases:
    """Edge case tests for SkillMemoryManager."""

    def _create_manager(self, **kwargs):
        """Create a SkillMemoryManager instance."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        defaults = {
            "core_skills": set(),
            "ttl_seconds": 300.0,
            "ttl_check_interval": 60.0,
            "max_loaded_skills": 10,
        }
        defaults.update(kwargs)

        manager = SkillMemoryManager(**defaults)
        unload_skill = MagicMock(return_value=True)
        return manager, unload_skill

    def test_empty_core_skills(self):
        """Test manager with no core skills."""
        manager, _ = self._create_manager(core_skills=set())

        manager.touch("skill_a")
        assert "skill_a" in manager.lru_timestamps

    def test_zero_ttl(self):
        """Test manager with zero TTL (immediate expiration)."""
        manager, _ = self._create_manager(ttl_seconds=0.0)

        manager.touch("skill")
        time.sleep(0.001)

        assert manager.is_ttl_expired("skill") is True

    def test_very_large_ttl(self):
        """Test manager with very large TTL."""
        manager, _ = self._create_manager(ttl_seconds=1_000_000_000)

        manager.touch("skill")
        assert manager.is_ttl_expired("skill") is False

    def test_multiple_touches_same_skill(self):
        """Test multiple touches on same skill."""
        manager, _ = self._create_manager()

        manager.touch("skill_a")
        manager.touch("skill_b")
        manager.touch("skill_a")
        manager.touch("skill_a")

        # skill_a should be last in LRU order
        assert manager.lru_order[-1] == "skill_a"
        assert len(manager.lru_order) == 2  # Only 2 unique skills

    def test_enforce_limit_with_zero_max_skills(self):
        """Test memory enforcement with zero max skills."""
        manager, unload_skill = self._create_manager(max_loaded_skills=0)

        loaded_skills = {"skill_1": MagicMock(), "skill_2": MagicMock()}
        pinned_skills = set()

        for name in loaded_skills:
            manager.touch(name)

        manager.enforce_memory_limit(loaded_skills, pinned_skills, unload_skill)

        # Should try to evict all non-pinned skills
        assert unload_skill.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_skills_with_no_loaded(self):
        """Test cleanup with no loaded skills."""
        manager, unload_skill = self._create_manager()

        await manager.cleanup_expired_skills({}, unload_skill)

        unload_skill.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_skills_removes_from_timestamps(self):
        """Test that cleanup removes expired skills from timestamps dict."""
        manager, unload_skill = self._create_manager(
            ttl_seconds=0.01,
            ttl_check_interval=0.0,
        )

        # Touch a skill but don't add to loaded_skills
        manager.touch("orphaned_skill")

        time.sleep(0.02)

        # Cleanup should remove it from timestamps
        await manager.cleanup_expired_skills({}, unload_skill)

        assert "orphaned_skill" not in manager.lru_timestamps
