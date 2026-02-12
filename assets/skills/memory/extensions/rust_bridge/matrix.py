"""
matrix.py - The Neural Matrix

High-performance memory grid for storing and retrieving episodic/semantic memory.
Uses Rust-powered vector store for embeddings and similarity search.
"""

import structlog
from pathlib import Path
from typing import Any

from .bindings import RustBindings

log = structlog.get_logger("omni.skill.memory.neural_matrix")


class NeuralMatrix:
    """
    [The Neural Matrix]

    High-performance memory grid that wraps RustVectorStore.
    Provides semantic memory storage and retrieval capabilities.
    """

    def __init__(self, skill_cwd: str = ".", dimension: int = 1536):
        """Initialize the Neural Matrix.

        Args:
            skill_cwd: Path to the skill directory (for storing .db files)
            dimension: Vector dimension (default: 1536 for OpenAI Ada-002)
        """
        self._skill_cwd = Path(skill_cwd)
        self._dimension = dimension
        self._store = None

        # Use unified database path API for consistency
        from omni.foundation.config.database import get_memory_db_path

        self._db_path = get_memory_db_path()

        # Initialize Rust vector store
        store_cls = RustBindings.get_store_class()
        if store_cls:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._store = store_cls(str(self._db_path), dimension, enable_keyword_index=True)
                log.info("Neural Matrix initialized", db_path=str(self._db_path))
            except Exception as e:
                log.error("Failed to initialize Neural Matrix", error=str(e))
                self._store = None

    @property
    def is_active(self) -> bool:
        """Check if the neural matrix is active."""
        return self._store is not None

    @property
    def backend(self) -> str:
        """Return the backend type."""
        return "omni-vector (Rust/LanceDB)" if self._store else "unavailable"

    def remember(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory.

        Args:
            content: The content to remember
            metadata: Optional metadata (tags, timestamp, etc.)

        Returns:
            Memory ID or status message
        """
        if not self._store:
            return "neural_matrix_offline"

        import uuid

        doc_id = str(uuid.uuid4())[:8]

        # Add timestamp if not present
        if metadata is None:
            metadata = {}
        metadata["_memory_id"] = doc_id
        metadata["_created_at"] = self._get_timestamp()

        # Store via Rust backend
        # Note: The actual embedding is handled by RustVectorStore
        try:
            # For now, use the async method synchronously
            import asyncio

            success = asyncio.run(
                self._store.ingest(
                    type(
                        "FileContent",
                        (),
                        {"path": doc_id, "content": content, "metadata": metadata},
                    )()
                )
            )
            if success.success:
                return f"memory_{doc_id}"
            return "store_failed"
        except Exception as e:
            return f"error: {e}"

    def recall(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Recall memories similar to the query.

        Args:
            query: The query to search for
            limit: Maximum number of results

        Returns:
            List of recalled memories with scores
        """
        if not self._store:
            return []

        try:
            import asyncio

            results = asyncio.run(self._store.search(query, limit=limit))
            return [
                {
                    "id": r.id,
                    "score": r.score,
                    "content": r.payload.get("content", ""),
                    "metadata": r.payload,
                }
                for r in results
            ]
        except Exception as e:
            log.error("Recall error", error=str(e))
            return []

    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        if not self._store:
            return {"active": False, "backend": "unavailable"}

        try:
            import asyncio

            healthy = asyncio.run(self._store.health_check())
            return {
                "active": healthy,
                "backend": self.backend,
                "db_path": str(self._db_path),
            }
        except Exception as e:
            return {"active": False, "backend": self.backend, "error": str(e)}

    @staticmethod
    def _get_timestamp() -> float:
        """Get current timestamp."""
        import time

        return time.time()


# Zero-Code Extension Protocol: Export as RustAccelerator
RustAccelerator = NeuralMatrix

__all__ = ["NeuralMatrix", "RustAccelerator"]
