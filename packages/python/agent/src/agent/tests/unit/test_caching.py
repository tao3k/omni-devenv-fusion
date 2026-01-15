"""
test_caching.py
Phase 61: Tests for Tool Result Caching functionality.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.core.skill_manager.caching import CacheEntry, ResultCacheMixin
from agent.core.skill_manager.models import Skill, SkillCommand


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            result="test result",
            timestamp=time.time(),
            dependency_mtime=1234.5,
            args_hash="abc123",
        )
        assert entry.result == "test result"
        assert entry.timestamp > 0
        assert entry.dependency_mtime == 1234.5
        assert entry.args_hash == "abc123"


class TestResultCacheMixin:
    """Tests for ResultCacheMixin."""

    def test_mixin_initialization(self):
        """Test that mixin initializes with empty cache."""
        mixin = ResultCacheMixin()
        assert mixin._result_cache == {}

    def test_cache_key_generation(self):
        """Test deterministic cache key generation."""
        mixin = ResultCacheMixin()

        key1 = mixin._get_cache_key("test_skill", "test_command", {"arg1": "value1"})
        key2 = mixin._get_cache_key("test_skill", "test_command", {"arg1": "value1"})
        key3 = mixin._get_cache_key("test_skill", "test_command", {"arg1": "value2"})

        # Same args should produce same key
        assert key1 == key2
        # Different args should produce different key
        assert key1 != key3

    def test_cache_key_order_independent(self):
        """Test that cache key is independent of arg order."""
        mixin = ResultCacheMixin()

        key1 = mixin._get_cache_key("skill", "cmd", {"a": 1, "b": 2})
        key2 = mixin._get_cache_key("skill", "cmd", {"b": 2, "a": 1})

        assert key1 == key2

    def test_try_get_cached_result_no_cache(self):
        """Test cache miss when no cache entry exists."""
        mixin = ResultCacheMixin()

        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 1000.0

        command = MagicMock(spec=SkillCommand)
        command.cache_ttl = 0.0

        result = mixin._try_get_cached_result(skill, command, {"arg": "value"})
        assert result is None

    def test_try_get_cached_result_ttl_expired(self):
        """Test cache invalidation when TTL expires."""
        mixin = ResultCacheMixin()

        # Create a skill with old mtime
        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 1000.0

        # Create a command with TTL
        command = MagicMock(spec=SkillCommand)
        command.cache_ttl = 1.0  # 1 second TTL

        # Manually add an expired entry
        key = mixin._get_cache_key("test_skill", "test_command", {})
        mixin._result_cache[key] = CacheEntry(
            result="cached",
            timestamp=time.time() - 10,  # 10 seconds ago (expired)
            dependency_mtime=1000.0,
            args_hash=key,
        )

        result = mixin._try_get_cached_result(skill, command, {})
        assert result is None  # Cache should be invalidated

    def test_try_get_cached_result_mtime_changed(self):
        """Test cache invalidation when skill mtime changes."""
        mixin = ResultCacheMixin()

        # Create a skill with new mtime
        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 2000.0  # Newer than cached

        # Create a command with TTL
        command = MagicMock(spec=SkillCommand)
        command.cache_ttl = 3600.0  # 1 hour TTL

        # Manually add an entry with old mtime
        key = mixin._get_cache_key("test_skill", "test_command", {})
        mixin._result_cache[key] = CacheEntry(
            result="cached",
            timestamp=time.time(),
            dependency_mtime=1000.0,  # Older than current skill mtime
            args_hash=key,
        )

        result = mixin._try_get_cached_result(skill, command, {})
        assert result is None  # Cache should be invalidated

    def test_try_get_cached_result_hit(self):
        """Test successful cache hit."""
        mixin = ResultCacheMixin()

        # Create a skill
        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 1000.0

        # Create a command with TTL (use real string value, not MagicMock)
        command = SkillCommand(
            name="test_command",
            func=lambda: None,
            cache_ttl=3600.0,  # 1 hour TTL
        )

        # Manually add a valid entry
        key = mixin._get_cache_key("test_skill", "test_command", {"arg": "value"})
        mixin._result_cache[key] = CacheEntry(
            result="cached result",
            timestamp=time.time(),
            dependency_mtime=1000.0,  # Same as skill mtime
            args_hash=key,
        )

        result = mixin._try_get_cached_result(skill, command, {"arg": "value"})
        assert result == "cached result"

    def test_store_cached_result(self):
        """Test storing a result in cache."""
        mixin = ResultCacheMixin()

        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 1000.0

        command = SkillCommand(
            name="test_command",
            func=lambda: None,
            cache_ttl=3600.0,
        )

        mixin._store_cached_result(skill, command, {"arg": "value"}, "new result")

        key = mixin._get_cache_key("test_skill", "test_command", {"arg": "value"})
        assert key in mixin._result_cache
        assert mixin._result_cache[key].result == "new result"

    def test_store_cached_result_disabled(self):
        """Test that storing is skipped when cache_ttl is 0."""
        mixin = ResultCacheMixin()

        skill = MagicMock(spec=Skill)
        skill.name = "test_skill"
        skill.mtime = 1000.0

        command = MagicMock(spec=SkillCommand)
        command.cache_ttl = 0.0  # Disabled

        mixin._store_cached_result(skill, command, {"arg": "value"}, "new result")

        assert len(mixin._result_cache) == 0

    def test_clear_cache(self):
        """Test clearing the cache."""
        mixin = ResultCacheMixin()

        # Add some entries
        mixin._result_cache["key1"] = MagicMock()
        mixin._result_cache["key2"] = MagicMock()

        mixin._clear_cache()

        assert len(mixin._result_cache) == 0


class TestSkillCommandCaching:
    """Tests for SkillCommand with caching fields."""

    def test_skill_command_with_cache_ttl(self):
        """Test creating a SkillCommand with cache_ttl."""

        async def dummy_func():
            return "result"

        command = SkillCommand(
            name="test_command",
            func=dummy_func,
            description="A test command",
            cache_ttl=60.0,
            pure=True,
        )

        assert command.cache_ttl == 60.0
        assert command.pure is True

    def test_skill_command_default_cache_ttl(self):
        """Test that default cache_ttl is 0 (disabled)."""

        async def dummy_func():
            return "result"

        command = SkillCommand(
            name="test_command",
            func=dummy_func,
        )

        assert command.cache_ttl == 0.0
        assert command.pure is False


class TestCachingIntegration:
    """Integration tests for caching in SkillManager context."""

    @pytest.mark.asyncio
    async def test_cached_command_execution(self):
        """Test that cached commands return cached results."""
        from agent.core.skill_manager.caching import ResultCacheMixin

        # Create a minimal class with just the cache mixin
        class CacheOnly(ResultCacheMixin):
            pass

        cache_holder = CacheOnly()
        cache_holder._result_cache.clear()

        # Create mock skill and command
        skill = MagicMock()
        skill.name = "test"
        skill.mtime = 1000.0

        command = MagicMock()
        command.cache_ttl = 60.0
        command.name = "cmd"

        # Store a cached result
        cache_holder._store_cached_result(skill, command, {}, "cached_value")

        # Should return cached result
        result = cache_holder._try_get_cached_result(skill, command, {})
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_uncached_command_execution(self):
        """Test that commands without TTL are not cached."""
        from agent.core.skill_manager.caching import ResultCacheMixin

        class CacheOnly(ResultCacheMixin):
            pass

        cache_holder = CacheOnly()
        cache_holder._result_cache.clear()

        skill = MagicMock()
        skill.name = "test"
        skill.mtime = 1000.0

        command = MagicMock()
        command.cache_ttl = 0.0  # Disabled
        command.name = "cmd"

        # Try to get cached result - should always return None
        result = cache_holder._try_get_cached_result(skill, command, {})
        assert result is None
