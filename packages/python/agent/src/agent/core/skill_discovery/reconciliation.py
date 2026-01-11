"""
src/agent/core/skill_discovery/reconciliation.py
Phase 36.6: Startup Reconciliation

Cleanup of "phantom skills" after crash or unclean shutdown.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def reconcile_index(loaded_skills: list[str]) -> dict[str, int]:
    """
    Phase 36.6: Startup reconciliation to prevent "Phantom Skills".

    After a crash or unclean shutdown, the index may contain skills that
    no longer exist on disk. This function cleans up those "ghost" entries.

    Flow:
    1. Get all skill IDs from the index
    2. Compare with actually loaded skills
    3. Delete index entries that don't match (phantom skills)
    4. (Optional) Re-index any loaded skills missing from index

    Args:
        loaded_skills: List of skill names that are currently loaded

    Returns:
        Dict with reconciliation stats: {"removed": N, "reindexed": N}
    """
    from agent.core.vector_store import get_vector_memory
    from .indexing import SKILL_REGISTRY_COLLECTION, index_single_skill

    logger.info("🔄 [Reconciliation] Starting index cleanup...")
    stats = {"removed": 0, "reindexed": 0}

    try:
        vm = get_vector_memory()
        collection = vm.client.get_collection(name=SKILL_REGISTRY_COLLECTION)

        # Get all local skill IDs from index (exclude remote skills)
        # Remote skills have IDs like "skill-remote-{name}"
        try:
            all_docs = collection.get(where={"type": "local"})
            indexed_ids = all_docs.get("ids", [])
        except Exception:
            # Collection might be empty
            indexed_ids = []

        # Build set of expected skill IDs
        expected_ids = {f"skill-{name}" for name in loaded_skills}

        # Find phantom skills (in index but not loaded)
        phantom_ids = [sid for sid in indexed_ids if sid not in expected_ids]

        if phantom_ids:
            collection.delete(ids=phantom_ids)
            stats["removed"] = len(phantom_ids)
            logger.info(
                f"🧹 [Reconciliation] Removed {len(phantom_ids)} phantom skills",
                phantoms=[pid.replace("skill-", "") for pid in phantom_ids],
            )
        else:
            logger.info("✅ [Reconciliation] No phantom skills found")

        # Optional: Re-index any loaded skills missing from index
        missing_skills = [name for name in loaded_skills if f"skill-{name}" not in indexed_ids]
        if missing_skills:
            logger.info(f"🔍 [Reconciliation] Re-indexing {len(missing_skills)} missing skills")
            for skill_name in missing_skills:
                success = await index_single_skill(skill_name)
                if success:
                    stats["reindexed"] += 1

    except Exception as e:
        logger.error(f"❌ [Reconciliation] Failed: {e}")

    logger.info(f"✅ [Reconciliation] Complete: {stats}")
    return stats


__all__ = [
    "reconcile_index",
]
