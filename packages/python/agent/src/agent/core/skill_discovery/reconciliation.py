"""
src/agent/core/skill_discovery/reconciliation.py
Phase 66: Startup Reconciliation (Simplified)

With Rust-backed sync_skills(), phantom skills are automatically handled.
sync_skills uses file hashes to determine what exists on disk.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def reconcile_index(loaded_skills: list[str]) -> dict[str, int]:
    """
    Phase 66: Simplified startup reconciliation.

    With Rust-backed sync_skills(), the reconciliation is simple:
    trigger incremental sync and it will automatically:
    - Remove deleted skills from index
    - Add new skills to index
    - Update modified skills

    Args:
        loaded_skills: List of skill names that are currently loaded (unused,
                       kept for interface compatibility)

    Returns:
        Dict with reconciliation stats from sync_skills
    """
    from agent.core.skill_discovery import reindex_skills_from_manifests

    logger.info("🔄 [Reconciliation] Starting incremental sync...")

    try:
        result = await reindex_skills_from_manifests()
        stats = result.get("stats", {})

        logger.info(
            f"✅ [Reconciliation] Complete: added={stats.get('added', 0)}, "
            f"modified={stats.get('modified', 0)}, deleted={stats.get('deleted', 0)}, "
            f"total={stats.get('total', 0)}"
        )

        return {
            "removed": stats.get("deleted", 0),
            "reindexed": stats.get("added", 0),
        }

    except Exception as e:
        logger.error(f"❌ [Reconciliation] Failed: {e}")
        return {"removed": 0, "reindexed": 0}


__all__ = [
    "reconcile_index",
]
