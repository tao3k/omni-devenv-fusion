"""
src/agent/core/skill_manager/caching.py
Phase 61: Tool Result Caching Mixin.

Implements intelligent caching for skill commands to reduce redundant IO.
Key components:
- Arg-aware cache keys
- TTL (Time-To-Live) enforcement
- Dependency Mtime invalidation (if skill code changes, cache invalidates)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import SkillCommand, Skill


@dataclass(slots=True)
class CacheEntry:
    """A single cache entry with metadata."""

    result: str
    timestamp: float
    dependency_mtime: float
    args_hash: str


class ResultCacheMixin:
    """
    Mixin to add intelligent caching to SkillManager.

    Strategies:
    1. Key = hash(skill + command + sorted_args)
    2. Validity Check:
       - Now < timestamp + TTL
       - Current Skill Mtime == Cached Dependency Mtime
    """

    __slots__ = ("_result_cache",)

    def __init__(self) -> None:
        self._result_cache: dict[str, CacheEntry] = {}

    def _get_cache_key(self, skill_name: str, command_name: str, args: dict[str, Any]) -> str:
        """Generate stable cache key from skill, command, and args."""
        # Sort args to ensure deterministic hashing
        try:
            args_str = json.dumps(args, sort_keys=True, default=str)
        except Exception:
            args_str = str(sorted(args.items()))

        raw = f"{skill_name}:{command_name}:{args_str}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _try_get_cached_result(
        self,
        skill: Skill,
        command: SkillCommand,
        args: dict[str, Any],
    ) -> str | None:
        """
        Attempt to retrieve result from cache.

        Returns None if cache miss or invalid (TTL expired or mtime changed).
        """
        if command.cache_ttl <= 0:
            return None

        key = self._get_cache_key(skill.name, command.name, args)
        entry = self._result_cache.get(key)

        if entry is None:
            return None

        # 1. TTL Check
        now = time.time()
        if now > entry.timestamp + command.cache_ttl:
            del self._result_cache[key]
            return None

        # 2. Dependency Mtime Check (Hot Reload Safety)
        # If the skill code has changed since caching, result might be stale
        if skill.mtime > entry.dependency_mtime:
            del self._result_cache[key]
            return None

        return entry.result

    def _store_cached_result(
        self,
        skill: Skill,
        command: SkillCommand,
        args: dict[str, Any],
        result: str,
    ) -> None:
        """Store result in cache if caching is enabled for this command."""
        if command.cache_ttl <= 0:
            return

        key = self._get_cache_key(skill.name, command.name, args)
        self._result_cache[key] = CacheEntry(
            result=result,
            timestamp=time.time(),
            dependency_mtime=skill.mtime,
            args_hash=key,
        )

    def _clear_cache(self) -> None:
        """Clear all cached results (useful for testing or reset)."""
        self._result_cache.clear()


__all__ = ["ResultCacheMixin", "CacheEntry"]
