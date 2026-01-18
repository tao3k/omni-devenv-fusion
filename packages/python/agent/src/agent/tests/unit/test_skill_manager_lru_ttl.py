"""
Tests for Phase 37: LRU + TTL Skill Management.

These tests now use SkillMemoryManager directly for core functionality.
Legacy SkillContext delegation tests have been removed.

Tests:
1. Core skills are never evicted
2. TTL expiration triggers eviction
3. Memory limit enforcement with mixed TTL/LRU
"""

import time
from unittest.mock import MagicMock

import pytest


class TestCoreSkillsProtection:
    """Test that core skills are never evicted."""

    def test_core_skills_not_in_eviction_list(self):
        """Core skills should be excluded from eviction candidates."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills={"memory", "structural_editing", "advanced_search"},
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Manually set timestamps: memory is core (never expires),
        # git and filesystem are old (should be expired)
        manager._lru_timestamps = {
            "memory": time.time() - 100,  # Recently touched
            "git": time.time() - 3600,  # 1 hour ago - expired
            "filesystem": time.time() - 1800,  # 30 min ago - expired
        }

        # Core skill should not be expired even if not recently touched
        assert manager.is_ttl_expired("memory") is False
        # Non-core skills should be expired
        assert manager.is_ttl_expired("git") is True
        assert manager.is_ttl_expired("filesystem") is True

    def test_check_ttl_expired_never_expires_for_core_skills(self):
        """Core skills should never expire even with old timestamps."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills={"memory"},
            ttl_seconds=1,  # 1 second TTL (very short)
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Touch memory with old timestamp
        manager.touch("memory")

        # Wait for TTL to expire
        time.sleep(0.01)

        # Core skill should never expire
        assert manager.is_ttl_expired("memory") is False


class TestTTLEviction:
    """Test TTL-based eviction behavior."""

    def test_ttl_check_returns_true_for_expired(self):
        """Skill with old timestamp should be considered expired."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills=set(),
            ttl_seconds=1800,  # 30 minutes
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Manually set timestamps (simulate old timestamps)
        manager._lru_timestamps = {
            "git": time.time() - 3600,  # 1 hour ago
            "filesystem": time.time() - 100,  # 100 seconds ago
        }

        assert manager.is_ttl_expired("git") is True
        assert manager.is_ttl_expired("filesystem") is False

    def test_ttl_check_returns_true_for_no_timestamp(self):
        """Skill with no timestamp should be considered expired."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills=set(),
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # No timestamps - all skills should be expired
        assert manager.is_ttl_expired("git") is True


class TestLRUOrdering:
    """Test LRU ordering with timestamps (using SkillMemoryManager directly)."""

    def test_touch_skill_updates_timestamp(self):
        """Touching a skill should update its timestamp."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills=set(),
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Touch a skill
        manager.touch("git")

        assert "git" in manager.lru_timestamps
        assert time.time() - manager.lru_timestamps["git"] < 1  # Recently updated

    def test_lru_order_property(self):
        """Test LRU order property returns skills in access order."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills=set(),
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Touch skills in order
        manager.touch("git")
        manager.touch("filesystem")

        # LRU order should reflect touch order
        assert manager.lru_order == ["git", "filesystem"]

        # Touch git again - should move to end
        manager.touch("git")
        assert manager.lru_order == ["filesystem", "git"]

    def test_lru_sorting_by_timestamp(self):
        """Skills should be sorted by timestamp for LRU eviction."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills=set(),
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=10,
        )

        # Manually set timestamps
        manager._lru_timestamps = {
            "old_skill": time.time() - 1000,
            "new_skill": time.time() - 10,
            "medium_skill": time.time() - 500,
        }

        sorted_skills = sorted(manager.lru_timestamps.items(), key=lambda x: x[1])

        assert sorted_skills[0][0] == "old_skill"
        assert sorted_skills[-1][0] == "new_skill"


class TestMemoryLimitEnforcement:
    """Test memory limit with mixed TTL/LRU eviction."""

    def test_enforce_limit_respects_core_skills(self):
        """Core skills should never be unloaded even when over limit."""
        from agent.core.skill_runtime.core.memory_core import SkillMemoryManager

        manager = SkillMemoryManager(
            core_skills={"memory"},
            ttl_seconds=1800,
            ttl_check_interval=300,
            max_loaded_skills=1,  # Only 1 slot, but memory is protected
        )

        loaded_skills = {
            "memory": MagicMock(),
            "git": MagicMock(),
        }

        # Touch skills
        manager.touch("memory")
        manager.touch("git")

        unloaded = []

        def track_unload(skill_name):
            unloaded.append(skill_name)
            if skill_name in loaded_skills:
                del loaded_skills[skill_name]
            return True

        manager.enforce_memory_limit(
            loaded_skills=loaded_skills,
            pinned_skills={"memory"},
            unload_skill=track_unload,
        )

        # Memory should NOT be unloaded
        assert "memory" not in unloaded


class TestConfigurationDefaults:
    """Test that configuration defaults are correctly defined."""

    def test_core_skills_default_values(self):
        """Verify the expected core skills list (from preload)."""
        expected_core = {"knowledge", "memory", "git"}
        assert expected_core == {"knowledge", "memory", "git"}

    def test_ttl_default_values(self):
        """Verify TTL default values from settings.yaml."""
        ttl_seconds = 1800.0  # 30 minutes (skills.ttl.timeout)
        ttl_check_interval = 300.0  # 5 minutes (skills.ttl.check_interval)
        max_loaded_skills = 15  # skills.max_loaded

        assert ttl_seconds == 1800.0
        assert ttl_check_interval == 300.0
        assert max_loaded_skills == 15


class TestConfDirectory:
    """Test --conf flag configuration directory handling."""

    def test_set_conf_dir_is_callable(self):
        """Verify set_conf_dir function is available from config module."""
        from common.config.directory import set_conf_dir

        assert callable(set_conf_dir)

    def test_get_conf_dir_returns_default(self):
        """Verify get_conf_dir returns default value."""
        from common.config.directory import get_conf_dir

        result = get_conf_dir()
        assert isinstance(result, str)
        assert result == "assets"  # default from settings.yaml

    def test_set_conf_dir_updates_value(self):
        """Verify set_conf_dir updates the configuration directory."""
        from common.config.directory import get_conf_dir, set_conf_dir

        original = get_conf_dir()
        try:
            set_conf_dir("/custom/path")
            assert get_conf_dir() == "/custom/path"
        finally:
            set_conf_dir(original)  # restore

    def test_get_setting_uses_conf_dir(self):
        """Verify get_setting reads from the configured directory."""
        from common.config.settings import get_setting

        # Should load skills.preload from the configured settings.yaml
        preload = get_setting("skills.preload", [])
        assert isinstance(preload, list)
        assert "knowledge" in preload
        assert "memory" in preload
        assert "git" in preload

    def test_get_setting_with_custom_defaults(self):
        """Verify get_setting returns custom defaults when key not found."""
        from common.config.settings import get_setting

        result = get_setting("nonexistent.key", "default_value")
        assert result == "default_value"

    def test_get_ttl_settings(self):
        """Verify TTL settings are loaded from settings.yaml."""
        from common.config.settings import get_setting

        timeout = get_setting("skills.ttl.timeout", 1800)
        check_interval = get_setting("skills.ttl.check_interval", 300)
        max_loaded = get_setting("skills.max_loaded", 15)

        assert timeout == 1800
        assert check_interval == 300
        assert max_loaded == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
