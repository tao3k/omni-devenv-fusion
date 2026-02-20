"""Memory service using Rust-based self-evolving memory engine.

This module provides the Python interface to the omni-memory Rust crate,
which implements:
- Episode storage with vector similarity
- Q-Learning for utility-based selection
- Two-Phase Search (semantic + Q-value reranking)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import omni_core_rs as omni

from omni.foundation.config.prj import PRJ_DATA
from omni.foundation.services.embedding import embed_text

logger = logging.getLogger(__name__)


def _default_memory_path() -> str:
    """Resolve default memory path under PRJ_DATA_HOME."""
    return str(PRJ_DATA("omni-agent", "memory"))


# Workaround for lambda keyword
def _get_lambda(cfg: omni.PyTwoPhaseConfig) -> float:
    """Get lambda value from config (lambda is a reserved keyword)."""
    return getattr(cfg, "lambda")


@dataclass
class MemoryConfig:
    """Configuration for the self-evolving memory engine."""

    path: str = field(default_factory=_default_memory_path)
    embedding_dim: int = 384
    table_name: str = "episodes"
    # Two-phase search parameters
    k1: int = 20  # Phase 1: number of candidates
    k2: int = 5  # Phase 2: number of final results
    q_weight: float = 0.3  # Weight for Q-value (0=semantic only, 1=Q only)
    # Q-Learning parameters
    learning_rate: float = 0.2
    discount_factor: float = 0.95


@dataclass
class MemoryEpisode:
    """A single memory episode."""

    id: str
    intent: str
    experience: str
    outcome: str
    q_value: float = 0.5
    success_count: int = 0
    failure_count: int = 0

    @classmethod
    def from_pyepisode(cls, ep: omni.PyEpisode) -> MemoryEpisode:
        """Create from Python binding."""
        return cls(
            id=ep.id,
            intent=ep.intent,
            experience=ep.experience,
            outcome=ep.outcome,
            q_value=ep.q_value,
            success_count=ep.success_count,
            failure_count=ep.failure_count,
        )


class MemoryService:
    """Self-evolving memory service using Rust core.

    Provides:
    - Store episodes with intent encoding
    - Semantic recall with vector similarity
    - Two-phase recall with Q-value reranking
    - Q-Learning updates for experience utility
    """

    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or MemoryConfig()
        self._episodes_path = Path(self.config.path) / f"{self.config.table_name}.episodes.json"
        self._q_table_path = Path(self.config.path) / f"{self.config.table_name}.q_table.json"

        # Create Rust components
        self._encoder = omni.create_intent_encoder(self.config.embedding_dim)
        self._q_table = omni.create_q_table(
            self.config.learning_rate,
            self.config.discount_factor,
        )
        self._store = omni.create_episode_store(
            omni.PyStoreConfig(
                self.config.path,  # path
                self.config.embedding_dim,  # embedding_dim
                self.config.table_name,  # table_name
            )
        )

        # Create two-phase search (positional args for lambda)
        self._search = omni.create_two_phase_search(
            self._q_table,
            self._encoder,
            omni.PyTwoPhaseConfig(
                self.config.k1,
                self.config.k2,
                self.config.q_weight,
            ),
        )
        self._load_state()

    def _save_state(self) -> None:
        """Persist episodes and Q-table to configured state files."""
        try:
            self._episodes_path.parent.mkdir(parents=True, exist_ok=True)
            self._store.save(str(self._episodes_path))
            self._store.save_q_table(str(self._q_table_path))
        except Exception as error:
            logger.warning("memory state save failed: %s", error)

    def _load_state(self) -> None:
        """Load persisted state if present."""
        try:
            if self._episodes_path.exists():
                self._store.load(str(self._episodes_path))
            if self._q_table_path.exists():
                self._store.load_q_table(str(self._q_table_path))
        except Exception as error:
            logger.warning("memory state load failed: %s", error)

    def store_episode(
        self,
        intent: str,
        experience: str,
        outcome: str,
        episode_id: str | None = None,
    ) -> str:
        """Store a new episode in memory.

        Args:
            intent: The user's intent/query
            experience: The actual experience/response
            outcome: The outcome (success/failure)
            episode_id: Optional custom ID

        Returns:
            The episode ID
        """
        if episode_id is None:
            episode_id = str(uuid.uuid4())

        # Try to use real embeddings from embedding service, fallback to Rust hash encoder
        try:
            embedding = embed_text(intent)
        except Exception:
            # Fallback: use Rust's built-in hash encoder
            encoder = omni.create_intent_encoder(self.config.embedding_dim)
            embedding = list(encoder.encode(intent))

        ep = omni.create_episode_with_embedding(
            episode_id,
            intent,
            experience,
            outcome,
            embedding,
        )
        self._store.store(ep)
        self._save_state()
        return episode_id

    def recall(self, query: str, k: int = 5) -> list[tuple[MemoryEpisode, float]]:
        """Semantic recall - find similar episodes by intent.

        Args:
            query: The query intent
            k: Number of results to return

        Returns:
            List of (episode, similarity_score) tuples
        """
        # Try to use real embeddings, fallback to Rust hash encoder
        try:
            embedding = embed_text(query)
        except Exception:
            encoder = omni.create_intent_encoder(self.config.embedding_dim)
            embedding = list(encoder.encode(query))
        results = self._store.recall_with_embedding(embedding, k)
        return [(MemoryEpisode.from_pyepisode(ep), score) for ep, score in results]

    def two_phase_recall(
        self,
        query: str,
        k1: int | None = None,
        k2: int | None = None,
        q_weight: float | None = None,
    ) -> list[tuple[MemoryEpisode, float]]:
        """Two-phase recall - semantic + Q-value reranking.

        Phase 1: Semantic recall (vector similarity)
        Phase 2: Q-value reranking (utility-based)

        Args:
            query: The query intent
            k1: Number of candidates from phase 1
            k2: Number of final results after phase 2
            q_weight: Weight for Q-value (0=semantic only, 1=Q only)

        Returns:
            List of (episode, combined_score) tuples
        """
        k1 = k1 if k1 is not None else self.config.k1
        k2 = k2 if k2 is not None else self.config.k2
        qw = q_weight if q_weight is not None else self.config.q_weight

        # Try to use real embeddings, fallback to Rust hash encoder
        try:
            embedding = embed_text(query)
        except Exception:
            encoder = omni.create_intent_encoder(self.config.embedding_dim)
            embedding = list(encoder.encode(query))
        results = self._store.two_phase_recall_with_embedding(embedding, k1, k2, qw)
        return [(MemoryEpisode.from_pyepisode(ep), score) for ep, score in results]

    def multi_hop_recall(
        self,
        queries: list[str],
        k: int | None = None,
        q_weight: float | None = None,
    ) -> list[tuple[MemoryEpisode, float]]:
        """Multi-hop reasoning - chain multiple queries together.

        Each hop uses results from previous hop to inform next search.
        This enables complex reasoning across related concepts.

        Args:
            queries: List of queries for each hop
            k: Number of results per hop
            q_weight: Weight for Q-value in two-phase search

        Returns:
            List of (episode, combined_score) tuples
        """
        k = k if k is not None else self.config.k2
        qw = q_weight if q_weight is not None else self.config.q_weight

        # Convert queries to embeddings
        embeddings = []
        for query in queries:
            try:
                embedding = embed_text(query)
            except Exception:
                encoder = omni.create_intent_encoder(self.config.embedding_dim)
                embedding = list(encoder.encode(query))
            embeddings.append(embedding)

        results = self._store.multi_hop_recall_with_embeddings(embeddings, k, qw)
        return [(MemoryEpisode.from_pyepisode(ep), score) for ep, score in results]

    def update_q_value(self, episode_id: str, reward: float) -> float:
        """Update Q-value for an episode using Q-Learning.

        Q_new = Q_old + learning_rate * (reward - Q_old)

        Args:
            episode_id: The episode ID
            reward: The reward signal (0.0 to 1.0)

        Returns:
            The new Q-value
        """
        updated = self._store.update_q(episode_id, reward)
        self._save_state()
        return updated

    def mark_success(self, episode_id: str) -> None:
        """Mark an episode as successful (increments success count)."""
        ep = self._store.get(episode_id)
        if ep:
            ep.mark_success()
            # Update Q-value based on outcome
            self.update_q_value(episode_id, 1.0)

    def mark_failure(self, episode_id: str) -> None:
        """Mark an episode as failed (increments failure count)."""
        ep = self._store.get(episode_id)
        if ep:
            ep.mark_failure()
            # Update Q-value based on outcome
            self.update_q_value(episode_id, 0.0)

    def get_episode(self, episode_id: str) -> MemoryEpisode | None:
        """Get an episode by ID."""
        ep = self._store.get(episode_id)
        if ep:
            return MemoryEpisode.from_pyepisode(ep)
        return None

    def get_all_episodes(self) -> list[MemoryEpisode]:
        """Get all stored episodes."""
        return [MemoryEpisode.from_pyepisode(ep) for ep in self._store.get_all()]

    def len(self) -> int:
        """Get the number of stored episodes."""
        return self._store.len()

    def is_empty(self) -> bool:
        """Check if memory is empty."""
        return self._store.is_empty()

    def calculate_score(self, similarity: float, q_value: float, q_weight: float) -> float:
        """Calculate combined score for an episode.

        score = (1 - λ) * similarity + λ * q_value

        Args:
            similarity: Semantic similarity score
            q_value: Q-value from learning
            q_weight: Weight for Q-value

        Returns:
            Combined score
        """
        return omni.calculate_score(similarity, q_value, q_weight)


# Global singleton instance
_memory_service: MemoryService | None = None


def get_memory_service(config: MemoryConfig | None = None) -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService(config)
    return _memory_service


def reset_memory_service() -> None:
    """Reset the global memory service (for testing)."""
    global _memory_service
    _memory_service = None
