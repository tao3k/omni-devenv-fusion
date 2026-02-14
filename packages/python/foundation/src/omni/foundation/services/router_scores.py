"""Router DB score persistence.

Writes search-algorithm scores only to router.lance (no duplication of skills content).
See docs/reference/skills-and-router-databases.md.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.router_scores")

ROUTER_SCORES_TABLE = "scores"


async def init_router_db(router_path: str, dimension: int = 1024) -> bool:
    """Ensure router DB exists and has a 'scores' table.

    Writes one placeholder row so the table is created. Non-fatal on error.
    """
    try:
        from omni.foundation.bridge import get_vector_store

        store = get_vector_store(index_path=router_path, dimension=dimension)
        await store.add_documents(
            ROUTER_SCORES_TABLE,
            ["_init"],
            [[0.0] * dimension],
            [""],
            ['{"_init": true}'],
        )
        logger.debug("Router DB initialized: %s", router_path)
        return True
    except Exception as e:
        logger.debug("Router DB init skipped: %s", e)
        return False


async def persist_router_scores(
    router_path: str,
    results: list[dict[str, Any]],
    query: str,
    dimension: int = 1024,
) -> int:
    """Append score rows to router.lance 'scores' table.

    Each row metadata: tool_id, vector_score, keyword_score, final_score, query_hash, ts.
    Uses dummy vectors; only scores are stored (no tool content).
    """
    if not results:
        return 0
    try:
        from omni.foundation.bridge import get_vector_store

        store = get_vector_store(index_path=router_path, dimension=dimension)
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        ts = int(time.time())
        ids = []
        vectors = []
        contents = []
        metadatas = []
        for i, r in enumerate(results):
            tool_id = r.get("tool_name") or r.get("id") or ""
            ids.append(f"{query_hash}_{tool_id}_{ts}_{i}")
            vectors.append([0.0] * dimension)
            contents.append("")
            meta = {
                "tool_id": tool_id,
                "vector_score": r.get("vector_score"),
                "keyword_score": r.get("keyword_score"),
                "final_score": r.get("final_score"),
                "score": r.get("score"),
                "query_hash": query_hash,
                "ts": ts,
            }
            metadatas.append(json.dumps(meta))
        await store.add_documents(
            ROUTER_SCORES_TABLE,
            ids,
            vectors,
            contents,
            metadatas,
        )
        logger.debug("Persisted %d scores to router DB", len(results))
        return len(results)
    except Exception as e:
        logger.debug("Router score persist skipped: %s", e)
        return 0
