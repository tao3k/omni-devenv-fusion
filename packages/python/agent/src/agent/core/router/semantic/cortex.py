# agent/core/router/semantic/cortex.py
"""
Semantic Cortex - Vector-based fuzzy matching for routing.

Lazy wrapper for SemanticCortex - defers vector_store initialization.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from agent.core.router.models import RoutingResult

# Lazy logger
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class _LazySemanticCortex:
    """Lazy wrapper for SemanticCortex - defers vector_store initialization."""

    COLLECTION_NAME = "routing_experience"
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

    def __init__(
        self,
        similarity_threshold: float | None = None,
        ttl_seconds: int | None = None,
    ):
        self.similarity_threshold = similarity_threshold or self.DEFAULT_SIMILARITY_THRESHOLD
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self._vector_store: Any = None

    @property
    def vector_store(self) -> Any:
        """Lazy vector_store accessor."""
        if self._vector_store is None:
            from agent.core.vector_store import get_vector_memory

            try:
                self._vector_store = get_vector_memory()
            except Exception as e:
                _get_logger().warning("Could not initialize vector store", error=str(e))
                self._vector_store = None
        return self._vector_store

    @vector_store.setter
    def vector_store(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._vector_store = value

    def _similarity_to_score(self, distance: float) -> float:
        """Convert distance to similarity score."""
        return 1.0 - distance

    def _is_expired(self, timestamp_str: str) -> bool:
        """Check if a timestamp is expired based on TTL."""
        try:
            timestamp = float(timestamp_str)
            return (time.time() - timestamp) > self.ttl_seconds
        except (ValueError, TypeError):
            return False

    async def recall(self, query: str) -> Optional[RoutingResult]:
        """
        Recall a routing result from semantic memory.

        Args:
            query: The query to recall

        Returns:
            RoutingResult if found and valid, None otherwise
        """
        if not self.vector_store:
            return None

        try:
            results = await self.vector_store.search(
                query=query, n_results=1, collection=self.COLLECTION_NAME
            )

            if not results:
                return None

            best = results[0]
            similarity = self._similarity_to_score(best.distance)

            metadata = best.metadata
            if "timestamp" in metadata and self._is_expired(metadata["timestamp"]):
                return None

            if similarity >= self.similarity_threshold:
                if "routing_result_json" in metadata:
                    data = json.loads(metadata["routing_result_json"])
                    return RoutingResult(
                        selected_skills=data.get("skills", []),
                        mission_brief=data.get("mission_brief", ""),
                        reasoning=data.get("reasoning", ""),
                        confidence=data.get("confidence", 0.5),
                        from_cache=True,
                        timestamp=data.get("timestamp", time.time()),
                    )

            return None

        except Exception as e:
            _get_logger().warning("Semantic recall failed", error=str(e))
            return None

    async def learn(self, query: str, result: RoutingResult) -> None:
        """
        Learn a routing result into semantic memory.

        Args:
            query: The query that triggered this routing
            result: The routing result to store
        """
        if not self.vector_store:
            return

        try:
            import uuid

            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, query))

            await self.vector_store.add(
                documents=[query],
                ids=[doc_id],
                collection=self.COLLECTION_NAME,
                metadatas=[
                    {
                        "routing_result_json": json.dumps(result.to_dict()),
                        "timestamp": str(result.timestamp),
                    }
                ],
            )
        except Exception as e:
            _get_logger().warning("Semantic learning failed", error=str(e))


# Backward compatibility alias
SemanticCortex = _LazySemanticCortex
