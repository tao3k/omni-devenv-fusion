"""
Tests for omni.core.cache.tool_schema
"""

import time
import pytest
from unittest.mock import patch


class TestToolSchemaCache:
    """Test ToolSchemaCache class."""

    def test_basic_get_set(self):
        """Test basic get and set operations."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache(ttl_seconds=300)
        schema = {"name": "test_tool", "input_schema": {}}

        cache.set("test.tool", schema)
        result = cache.get("test.tool")

        assert result == schema
        assert result is not schema  # Should be a copy

    def test_get_nonexistent(self):
        """Test getting nonexistent key returns None."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache()
        result = cache.get("nonexistent.tool")

        assert result is None

    def test_expiration(self):
        """Test that entries expire after TTL."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache(ttl_seconds=1)  # 1 second TTL
        schema = {"name": "expired_tool"}

        cache.set("tool", schema)
        assert cache.get("tool") == schema

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get("tool") is None
        assert cache.size == 0

    def test_invalidate_specific(self):
        """Test invalidating specific entry."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache()
        cache.set("tool1", {"name": "tool1"})
        cache.set("tool2", {"name": "tool2"})

        assert cache.size == 2

        cache.invalidate("tool1")

        assert cache.get("tool1") is None
        assert cache.get("tool2") == {"name": "tool2"}
        assert cache.size == 1

    def test_invalidate_all(self):
        """Test invalidating all entries."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache()
        cache.set("tool1", {"name": "tool1"})
        cache.set("tool2", {"name": "tool2"})
        cache.set("tool3", {"name": "tool3"})

        assert cache.size == 3

        cache.invalidate()

        assert cache.size == 0
        assert cache.get("tool1") is None
        assert cache.get("tool2") is None

    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache(ttl_seconds=1)
        cache.set("tool1", {"name": "tool1"})
        cache.set("tool2", {"name": "tool2"})
        cache.set("tool3", {"name": "tool3"})

        # Wait for expiration
        time.sleep(1.1)

        count = cache.cleanup_expired()
        assert count == 3
        assert cache.size == 0

    def test_thread_safety(self):
        """Test thread-safe operations."""
        from omni.core.cache.tool_schema import ToolSchemaCache
        import threading

        cache = ToolSchemaCache()
        errors = []

        def set_items():
            try:
                for i in range(100):
                    cache.set(f"tool.{i}", {"name": f"tool_{i}"})
            except Exception as e:
                errors.append(e)

        def get_items():
            try:
                for _ in range(100):
                    cache.get("tool.50")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_items) for _ in range(3)] + [
            threading.Thread(target=get_items) for _ in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_get_ttl(self):
        """Test getting TTL value."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache(ttl_seconds=600)
        assert cache.get_ttl() == 600

    def test_set_ttl(self):
        """Test setting TTL value."""
        from omni.core.cache.tool_schema import ToolSchemaCache

        cache = ToolSchemaCache(ttl_seconds=300)
        cache.set_ttl(600)
        assert cache.get_ttl() == 600


class TestGetSchemaCache:
    """Test get_schema_cache function."""

    def test_singleton_behavior(self):
        """Test that cache is a singleton."""
        from omni.core.cache.tool_schema import get_schema_cache, reset_cache

        reset_cache()

        cache1 = get_schema_cache()
        cache2 = get_schema_cache()

        assert cache1 is cache2

    def test_resets_on_reset(self):
        """Test that reset clears the singleton."""
        from omni.core.cache.tool_schema import get_schema_cache, reset_cache

        reset_cache()

        cache1 = get_schema_cache()
        cache1.set("test", {"name": "test"})

        reset_cache()

        cache2 = get_schema_cache()
        assert cache2.get("test") is None


class TestGetCachedSchema:
    """Test get_cached_schema function."""

    def test_cache_hit(self):
        """Test cache hit returns cached value."""
        from omni.core.cache.tool_schema import get_cached_schema, reset_cache

        reset_cache()

        call_count = 0

        def extractor():
            nonlocal call_count
            call_count += 1
            return {"name": "cached_tool", "count": call_count}

        schema1 = get_cached_schema("tool.test", extractor)
        schema2 = get_cached_schema("tool.test", extractor)

        assert schema1 == {"name": "cached_tool", "count": 1}
        assert schema2 == {"name": "cached_tool", "count": 1}  # Same cached value
        assert call_count == 1  # Extractor only called once

    def test_cache_miss(self):
        """Test cache miss calls extractor."""
        from omni.core.cache.tool_schema import get_cached_schema, reset_cache

        reset_cache()

        call_count = 0

        def extractor():
            nonlocal call_count
            call_count += 1
            return {"name": "new_tool", "count": call_count}

        schema = get_cached_schema("tool.new", extractor)

        assert schema == {"name": "new_tool", "count": 1}
        assert call_count == 1
