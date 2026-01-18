"""
_modules/_memory/ - Skill Memory Management Module

Migrated from manager.py LRU/TTL functionality.
Provides memory management for skill lifecycle.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable


class SkillMemoryManager:
    """
    Manages skill memory with LRU eviction and TTL expiration.

    Features:
    - LRU-based eviction when memory limit exceeded
    - TTL-based expiration for unused skills
    - Background cleanup task
    """

    __slots__ = (
        "_lru_timestamps",
        "_lru_order",
        "_core_skills",
        "_ttl_seconds",
        "_ttl_check_interval",
        "_max_loaded_skills",
        "_last_ttl_check",
        "_ttl_cleanup_task",
    )

    def __init__(
        self,
        core_skills: set[str],
        ttl_seconds: float,
        ttl_check_interval: float,
        max_loaded_skills: int,
    ) -> None:
        self._lru_timestamps: dict[str, float] = {}
        self._lru_order: list[str] = []
        self._core_skills = core_skills
        self._ttl_seconds = ttl_seconds
        self._ttl_check_interval = ttl_check_interval
        self._max_loaded_skills = max_loaded_skills
        self._last_ttl_check: float = 0.0
        self._ttl_cleanup_task: asyncio.Task | None = None

    # =========================================================================
    # LRU Tracking
    # =========================================================================

    def touch(self, skill_name: str) -> None:
        """Mark a skill as recently used (updates timestamp for LRU + TTL)."""
        self._lru_timestamps[skill_name] = time.time()
        if skill_name in self._lru_order:
            self._lru_order.remove(skill_name)
        self._lru_order.append(skill_name)

    @property
    def lru_order(self) -> list[str]:
        """Get LRU order list."""
        return self._lru_order

    @property
    def lru_timestamps(self) -> dict[str, float]:
        """Get LRU timestamps dict."""
        return self._lru_timestamps

    # =========================================================================
    # TTL Check
    # =========================================================================

    def is_ttl_expired(self, skill_name: str) -> bool:
        """Check if a skill's TTL has expired."""
        if skill_name in self._core_skills:
            return False
        if skill_name not in self._lru_timestamps:
            return True
        elapsed = time.time() - self._lru_timestamps[skill_name]
        return elapsed > self._ttl_seconds

    @property
    def ttl_seconds(self) -> float:
        """Get TTL seconds."""
        return self._ttl_seconds

    @property
    def ttl_check_interval(self) -> float:
        """Get TTL check interval."""
        return self._ttl_check_interval

    # =========================================================================
    # Memory Limit Enforcement
    # =========================================================================

    def enforce_memory_limit(
        self,
        loaded_skills: dict[str, Any],
        pinned_skills: set[str],
        unload_skill: Callable[[str], bool],
    ) -> int:
        """
        Unload skills if loaded count exceeds limit.

        Args:
            loaded_skills: Dictionary of loaded skills
            pinned_skills: Set of pinned/core skill names
            unload_skill: Callback to unload a skill

        Returns:
            Number of skills unloaded
        """
        import structlog

        logger = structlog.get_logger(__name__)
        current_time = time.time()

        unloaded = 0

        # Step 1: Cleanup TTL-expired skills first
        for skill_name in list(self._lru_timestamps.keys()):
            if skill_name in pinned_skills:
                continue
            if skill_name not in self._lru_timestamps:
                continue
            elapsed = current_time - self._lru_timestamps[skill_name]
            if elapsed > self._ttl_seconds:
                if skill_name not in loaded_skills:
                    continue
                logger.debug(
                    "TTL Eviction: Removing expired skill",
                    skill=skill_name,
                    elapsed_seconds=int(elapsed),
                    ttl_seconds=int(self._ttl_seconds),
                )
                if unload_skill(skill_name):
                    unloaded += 1

        # Step 2: Check if still over limit after TTL cleanup
        if len(loaded_skills) <= self._max_loaded_skills:
            return unloaded

        # Step 3: Unload oldest LRU skills if still over limit
        excess = len(loaded_skills) - self._max_loaded_skills
        lru_unloaded = 0

        sorted_skills = sorted(
            [(name, ts) for name, ts in self._lru_timestamps.items()],
            key=lambda x: x[1],
        )

        for skill_name, _ in sorted_skills:
            if lru_unloaded >= excess:
                break
            if skill_name in pinned_skills:
                continue
            if skill_name not in loaded_skills:
                continue

            logger.debug(
                "LRU Eviction: Releasing unused skill",
                skill=skill_name,
                loaded_count=len(loaded_skills),
                limit=self._max_loaded_skills,
            )

            if unload_skill(skill_name):
                lru_unloaded += 1

        logger.debug(
            "Memory limit enforcement complete",
            ttl_unloaded=unloaded,
            lru_unloaded=lru_unloaded,
            remaining=len(loaded_skills),
        )

        return unloaded + lru_unloaded

    # =========================================================================
    # TTL Cleanup
    # =========================================================================

    async def cleanup_expired_skills(
        self,
        loaded_skills: dict[str, Any],
        unload_skill: Callable[[str], bool],
    ) -> int:
        """
        Cleanup skills that have exceeded their TTL.

        Args:
            loaded_skills: Dictionary of loaded skills
            unload_skill: Callback to unload a skill

        Returns:
            Number of skills cleaned up
        """
        import structlog

        logger = structlog.get_logger(__name__)
        current_time = time.time()

        # Skip if within check interval
        if current_time - self._last_ttl_check < self._ttl_check_interval:
            return 0

        self._last_ttl_check = current_time

        # Find expired skills
        expired_skills = [
            name
            for name, timestamp in self._lru_timestamps.items()
            if name not in self._core_skills and (current_time - timestamp) > self._ttl_seconds
        ]

        cleaned = 0
        for skill_name in expired_skills:
            if skill_name in loaded_skills:
                logger.debug(
                    "TTL Eviction: Removing expired skill",
                    skill=skill_name,
                    ttl_seconds=int(self._ttl_seconds),
                )
                if unload_skill(skill_name):
                    cleaned += 1
            else:
                del self._lru_timestamps[skill_name]

        if cleaned > 0:
            logger.info(
                "TTL cleanup complete",
                cleaned=cleaned,
                remaining=len(loaded_skills),
            )

        return cleaned

    @property
    def last_ttl_check(self) -> float:
        """Get last TTL check timestamp."""
        return self._last_ttl_check

    @last_ttl_check.setter
    def last_ttl_check(self, value: float) -> None:
        """Set last TTL check timestamp."""
        self._last_ttl_check = value

    @property
    def max_loaded_skills(self) -> int:
        """Get max loaded skills limit."""
        return self._max_loaded_skills


__all__ = ["SkillMemoryManager"]
