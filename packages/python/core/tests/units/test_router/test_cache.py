"""Tests for omni.core.router.cache module."""

from __future__ import annotations

import time

import pytest

from omni.core.router.cache import SearchCache


class TestSearchCache:
    """Test SearchCache class."""

    def test_default_initialization(self):
        """Test default cache initialization."""
        cache = SearchCache()

        assert cache._max_size == 1000
        assert cache._ttl == 300
        assert len(cache) == 0

    def test_custom_initialization(self):
        """Test custom cache initialization."""
        cache = SearchCache(max_size=100, ttl=60)

        assert cache._max_size == 100
        assert cache._ttl == 60

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = SearchCache()
        results = [{"id": "1", "score": 0.9}, {"id": "2", "score": 0.8}]

        cache.set("test query", results)
        retrieved = cache.get("test query")

        assert retrieved == results
        assert len(cache) == 1

    def test_get_nonexistent(self):
        """Test getting nonexistent query returns None."""
        cache = SearchCache()

        result = cache.get("nonexistent")
        assert result is None

    def test_cache_hit(self):
        """Test cache hit increases usage."""
        cache = SearchCache()
        cache.set("query", ["result"])

        # First get
        result1 = cache.get("query")
        # Second get (should still work)
        result2 = cache.get("query")

        assert result1 == result2
        assert result2 == ["result"]

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SearchCache(max_size=2)

        cache.set("a", ["a"])
        cache.set("b", ["b"])
        cache.set("c", ["c"])  # Should evict "a"

        assert cache.get("a") is None  # Evicted
        assert cache.get("b") == ["b"]
        assert cache.get("c") == ["c"]

    def test_lru_access_order(self):
        """Test that accessing an entry moves it to most recent."""
        cache = SearchCache(max_size=2)

        cache.set("a", ["a"])
        cache.set("b", ["b"])
        cache.get("a")  # Access "a" to make it most recent
        cache.set("c", ["c"])  # Should evict "b" (least recent)

        assert cache.get("a") == ["a"]  # Still available
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") == ["c"]

    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = SearchCache(ttl=1)  # 1 second TTL

        cache.set("query", ["result"])
        assert cache.get("query") == ["result"]

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get("query") is None

    def test_clear(self):
        """Test clearing all entries."""
        cache = SearchCache()
        cache.set("a", ["a"])
        cache.set("b", ["b"])
        cache.set("c", ["c"])

        count = cache.clear()

        assert count == 3
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_remove_expired(self):
        """Test manual removal of expired entries."""
        cache = SearchCache(ttl=1)

        cache.set("query", ["result"])
        time.sleep(1.1)  # Ensure expired

        removed = cache.remove_expired()

        assert removed >= 1
        assert len(cache) == 0

    def test_stats(self):
        """Test getting cache statistics."""
        cache = SearchCache(max_size=100, ttl=60)
        cache.set("query", ["result"])

        stats = cache.stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 60
        assert "hit_rate" in stats

    def test_contains(self):
        """Test membership check."""
        cache = SearchCache()
        cache.set("query", ["result"])

        assert "query" in cache
        assert "nonexistent" not in cache

    def test_repr(self):
        """Test string representation."""
        cache = SearchCache(max_size=100, ttl=60)
        cache.set("a", ["a"])

        assert "SearchCache" in repr(cache)
        assert "100" in repr(cache)
        assert "60" in repr(cache)

    def test_empty_cache_len(self):
        """Test len() on empty cache."""
        cache = SearchCache()
        assert len(cache) == 0

    def test_len_after_operations(self):
        """Test len() after various operations."""
        cache = SearchCache(max_size=10)

        cache.set("a", ["a"])
        cache.set("b", ["b"])
        assert len(cache) == 2

        cache.set("a", ["a"])  # Update existing
        assert len(cache) == 2  # Same size

        cache.get("a")  # Access
        assert len(cache) == 2  # Same size

    def test_empty_results_caching(self):
        """Test caching empty results."""
        cache = SearchCache()

        cache.set("empty_query", [])

        # Empty results should still be cached
        result = cache.get("empty_query")
        assert result == []

    def test_complex_results(self):
        """Test caching complex result structures."""
        cache = SearchCache()

        complex_results = [
            {
                "id": "tool1",
                "name": "git.commit",
                "description": "Commit changes",
                "score": 0.95,
                "metadata": {
                    "skill": "git",
                    "category": "version_control",
                },
            },
            {
                "id": "tool2",
                "name": "git.commit_amend",
                "description": "Amend commit",
                "score": 0.85,
                "metadata": {"skill": "git"},
            },
        ]

        cache.set("commit", complex_results)
        retrieved = cache.get("commit")

        assert retrieved == complex_results
        assert retrieved[0]["metadata"]["skill"] == "git"


class TestSearchCacheEdgeCases:
    """Test edge cases for SearchCache."""

    def test_unicode_query(self):
        """Test caching with unicode queries."""
        cache = SearchCache()

        cache.set("中文查询", ["结果"])
        result = cache.get("中文查询")

        assert result == ["结果"]

    def test_long_query(self):
        """Test caching with very long queries."""
        cache = SearchCache()

        long_query = " ".join(["test"] * 1000)
        cache.set(long_query, ["result"])

        assert cache.get(long_query) == ["result"]

    def test_special_characters_in_query(self):
        """Test caching with special characters."""
        cache = SearchCache()

        special_query = 'test!@#$%^&*()[]{}|:"<>?'
        cache.set(special_query, ["result"])

        assert cache.get(special_query) == ["result"]

    def test_none_results_not_cached(self):
        """Test that None results are not explicitly rejected."""
        cache = SearchCache()
        # Setting None is technically allowed but typically not used
        cache.set("query", None)
        assert cache.get("query") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
