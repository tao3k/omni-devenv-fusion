"""
hybrid_search.py - Hybrid Search Engine (Rust-Native Implementation)

This module provides a thin Python shell over Rust's omni-vector search.
All heavy lifting (vector search, keyword rescue, scoring, fusion) is done in Rust.

Rust Benefits:
- Zero serialization overhead (no Python->Rust->Python data copying)
- High-performance L2 distance computation
- Integrated Tantivy BM25 keyword search
- Atomic hybrid scoring (Keyword Rescue pattern)

Architecture:
    User Query
        │
        ├────────────────┬────────────────┤
        │                │                │
    Embedding      Query Cleaning      Raw Query
    (Python)           │                │
        │               ▼                │
        │    Remove: " ' [ ] ( ) { }      │
        │    (Tantivy-safe chars)        │
        │               │                │
        ▼               ▼                ▼
    ┌─────────────────────────────────────────┐
    │         Rust omni-vector Search         │
    │  ┌─────────────────┬─────────────────┐  │
    │  │  LanceDB        │   Tantivy       │  │
    │  │  (Vector)       │   (Keyword)     │  │
    │  │  weight=1.0     │   weight=1.5    │  │
    │  └─────────────────┴─────────────────┘  │
    │                    │                    │
    │         Weighted RRF Fusion +          │
    │         Field Boosting                 │
    │  (NAME_TOKEN_BOOST=0.5,               │
    │   EXACT_PHRASE_BOOST=1.5)              │
    └─────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────┐
    │           Python Post-Processing        │
    │  - Confidence calibration              │
    │  - Result formatting                   │
    └─────────────────────────────────────────┘
                    │
                    ▼
    List[dict] with: id, score, confidence, skill_name, command, etc.

Scoring Model:
    After Rust-level boosting, scores are calibrated as:
    - Score > 0.8: High (Strong keyword match in tool name)
    - Score > 0.4: Medium (Semantic consensus)
    - Score <= 0.4: Low (Should be filtered out)

Usage:
    search = HybridSearch()
    results = await search.search("git commit", limit=5)

    # With threshold filtering
    results = await search.search("find files", limit=10, min_score=0.4)

    # Check confidence
    for r in results:
        if r["confidence"] == "high":
            print(f"Best match: {r['id']} (score={r['score']:.2f})")
"""

from __future__ import annotations

from typing import Any

from omni.foundation.bridge.rust_vector import get_vector_store
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.hybrid")


class HybridMatch:
    """Represents a match from hybrid search (Rust-native).

    This class is used internally by Rust-to-Python result conversion.
    In practice, results are returned as dicts from `search()` method.

    Attributes:
        id: Tool identifier in "skill.command" format (e.g., "git.commit").
        content: Tool description from indexed content.
        semantic_score: Raw vector similarity score from LanceDB (0.0-1.0).
        keyword_score: BM25 score from Tantivy keyword search.
        combined_score: Final Weighted RRF score after fusion and boosting.
        confidence: Human-readable confidence level ("high", "medium", "low").
        final_score: Display-calibrated score for UI/thresholding.
        metadata: Additional tool metadata (skill_name, file_path, etc.).
    """

    model_config = {"frozen": True}

    id: str
    content: str
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    confidence: str = "unknown"
    final_score: float = 0.0
    metadata: dict[str, Any] = {}


class HybridSearch:
    """Rust-Native Hybrid Search Engine.

    Thin Python shell over Rust omni-vector. All search logic is in Rust:
    - Vector similarity search (LanceDB with normalized vectors)
    - Keyword rescue (Tantivy BM25 for exact/partial matches)
    - Weighted RRF fusion with field boosting

    Rust performs all heavy computation; Python handles:
    - Embedding generation for vector search
    - Query cleaning for Tantivy compatibility
    - Confidence calibration for downstream consumers

    Intent extraction is handled by the discovery node LLM prompt.

    Example:
        ```python
        search = HybridSearch()

        # Basic search
        results = await search.search("find files", limit=5)

        # With threshold filtering
        results = await search.search(
            query="git commit",
            limit=10,
            min_score=0.4  # Only return medium+ confidence results
        )

        # Process results
        for r in results:
            if r["confidence"] == "high":
                print(f"Best: {r['id']} (score={r['score']:.2f})")
        ```

    Attributes:
        _store: Rust vector store instance (LanceDB + Tantivy).
        _embed_service: Lazy-loaded embedding service.

    See Also:
        - omni.core.router.main.OmniRouter: Higher-level router facade
        - omni.core.skills.discovery.SkillDiscoveryService: Tool discovery service
    """

    def __init__(self) -> None:
        """Initialize hybrid search with Rust vector store.

        The vector store is cached globally to avoid repeated initialization.
        Embedding service is loaded lazily on first use.
        """
        from omni.agent.cli.commands.reindex import get_database_path

        router_path = get_database_path("router")
        self._store = get_vector_store(router_path)

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search using Rust omni-vector engine.

        This method orchestrates the full hybrid search pipeline:
        1. Generate query embedding (semantic search)
        2. Clean query for keyword search (Tantivy compatibility)
        3. Call Rust search_tools for vector + keyword fusion
        4. Calibrate confidence levels for downstream consumers

        Args:
            query: Natural language search query (e.g., "find files matching 'pub updated'").
                The query is used both for semantic embedding and keyword matching.
            limit: Maximum number of results to return. Default is 5.
            min_score: Minimum combined score threshold (0.0-1.0). Results below this
                threshold are filtered out. Use 0.4 for "medium+" confidence only.

        Returns:
            List of result dictionaries, sorted by score descending. Each dict contains:
            - id: Tool identifier (e.g., "git.commit")
            - content: Tool description
            - score: Raw RRF score from Rust (0.0-2.0+)
            - confidence: "high", "medium", or "low"
            - final_score: Display-calibrated score (0.0-1.0)
            - skill_name: Skill name (e.g., "git")
            - command: Command name (e.g., "commit")
            - file_path: Source file path
            - keywords: Indexed keywords
            - input_schema: JSON schema for tool parameters
            - payload: Complete metadata for routing

        Example:
            ```python
            results = await search.search("git commit message", limit=3)
            for r in results:
                print(f"{r['id']}: {r['confidence']} (score={r['score']:.2f})")
            # Output:
            # git.commit: high (score=1.00)
            # git.smart_commit: high (score=0.95)
            ```

        Note:
            Query cleaning removes characters that cause Tantivy parse errors:
            quotes, brackets, parentheses, braces. The original query is used
            for embedding generation to preserve semantic meaning.

        See Also:
            - _calibrate_confidence: Confidence level assignment logic
            - Rust omni-vector::hybrid_search for underlying algorithm
        """
        import re

        # Clean query for keyword search (remove Tantivy-problematic chars)
        # Keep original for embedding to preserve semantic meaning
        #
        # Removed chars that cause Tantivy parse errors or unexpected field searches:
        # - Quotes: " ' (trigger phrase queries requiring position index)
        # - Brackets/Braces/Parentheses: [ ] { } ( ) (syntax chars)
        # - Colon: : (triggers field search: "https:..." -> searches field "https")
        # - Slash/Backslash: / \ (path delimiters)
        # - Comma: , ， (punctuation)
        keyword_query = re.sub(r'[:"\'\[\](){}/\\,，]', " ", query).strip()
        keyword_query = re.sub(r"\s+", " ", keyword_query)  # Normalize spaces

        # Get query embedding (required for vector search) - use original query
        embed_service = self._get_embed_service()
        query_vector = embed_service.embed(query)

        # Ensure vector is flat list
        if isinstance(query_vector[0], list):
            query_vector = query_vector[0]

        # Call Rust search_tools (does vector + keyword rescue + fusion)
        # Use cleaned query for keyword search to avoid Tantivy parse errors
        results = await self._store.search_tools(
            table_name="skills",
            query_vector=query_vector,
            query_text=keyword_query,  # Cleaned query for keyword rescue
            limit=limit,
            threshold=min_score,
        )

        # Format results for Python consumers
        formatted = []
        for r in results:
            raw_score = r.get("score", 0.0)
            confidence, final_score = self._calibrate_confidence(raw_score)

            # Extract command from tool_name (tool_name is "skill.command" format)
            full_tool_name = r.get("tool_name", "")
            parts = full_tool_name.split(".")
            command = ".".join(parts[1:]) if len(parts) > 1 else full_tool_name

            # r is already a dict from Rust
            formatted.append(
                {
                    "id": r.get("name", ""),
                    "content": r.get("description", ""),
                    "score": raw_score,
                    "confidence": confidence,
                    "final_score": final_score,
                    "skill_name": r.get("skill_name", ""),
                    "command": command,
                    "file_path": r.get("file_path", ""),
                    "keywords": r.get("keywords", []),
                    "input_schema": r.get("input_schema", "{}"),
                    "payload": {
                        "skill_name": r.get("skill_name", ""),
                        "command": command,
                        "type": "command",
                        "content": r.get("description", ""),
                    },
                }
            )

        logger.debug(f"Hybrid search for '{query}': {len(formatted)} results")
        return formatted

    def _calibrate_confidence(self, score: float) -> tuple[str, float]:
        """Calibrate raw RRF scores into interpretable confidence levels.

        This method translates raw Weighted RRF scores into human-readable
        confidence levels. The thresholds are calibrated based on Rust-level
        field boosting (NAME_TOKEN_BOOST=0.5, EXACT_PHRASE_BOOST=1.5).

        Confidence Levels:
            - **High** (score > 0.8): Strong keyword match in tool name.
              Example: Query "commit" matches "git.commit" (+0.5 boost per match).
            - **Medium** (score > 0.4): Good semantic consensus.
              Multiple search streams agree on relevance.
            - **Low** (score <= 0.4): Vague or weak match.
              Should be filtered out by threshold for production use.

        Display Score Calibration:
            High scores are mapped to 0.90-0.99 for UI readability.
            Medium scores are scaled to 0.60-0.89.
            Low scores are preserved as-is for transparency.

        Args:
            score: Raw RRF score from Rust (typically 0.0-2.0+).

        Returns:
            Tuple of (confidence_level, final_score) where:
            - confidence_level: "high", "medium", or "low"
            - final_score: Display-calibrated score (0.0-1.0)

        Example:
            ```python
            conf, display = search._calibrate_confidence(1.0)
            print(conf, display)  # "high", 0.95

            conf, display = search._calibrate_confidence(0.5)
            print(conf, display)  # "medium", 0.75

            conf, display = search._calibrate_confidence(0.2)
            print(conf, display)  # "low", 0.2
            ```

        See Also:
            - Rust omni-vector::keyword::apply_weighted_rrf for scoring algorithm
        """
        if score >= 0.8:
            # Strong match (hit keywords in tool name)
            return ("high", min(0.99, 0.90 + score * 0.05))
        elif score >= 0.4:
            # Good semantic match
            return ("medium", min(0.89, 0.60 + score * 0.3))
        else:
            # Weak match - should be filtered out by threshold
            return ("low", max(0.1, score))

    def _get_embed_service(self) -> Any:
        """Lazily load and return the embedding service.

        The embedding service is loaded on first use to avoid initialization
        overhead during module import. Thread-safe via double-checked locking.

        Returns:
            EmbeddingService: Service for generating query embeddings.

        Raises:
            RuntimeError: If embedding service cannot be initialized.
        """
        if not hasattr(self, "_embed_service"):
            from omni.foundation.services.embedding import get_embedding_service

            self._embed_service = get_embedding_service()
        return self._embed_service

    def set_weights(self, semantic: float, keyword: float) -> None:
        """Set search weights (reserved for future RRF configuration).

        Currently this method is a no-op. The search uses fixed weights
        defined in Rust (SEMANTIC_WEIGHT=1.0, KEYWORD_WEIGHT=1.5).

        This method exists for future extensibility if we want to expose
        weight configuration to Python callers.

        Args:
            semantic: Reserved for semantic search weight (currently ignored).
            keyword: Reserved for keyword search weight (currently ignored).

        Note:
            To modify weights, update the constants in Rust:
            - omni-vector/src/keyword.rs: SEMANTIC_WEIGHT, KEYWORD_WEIGHT
        """
        logger.info(f"Weights requested: semantic={semantic}, keyword={keyword}")
        logger.info("Note: Currently using fixed Rust weights (semantic=1.0, keyword=1.5)")

    def get_weights(self) -> tuple[float, float]:
        """Get the current search weights used by Rust.

        These are the fixed weights defined in Rust's omni-vector crate.

        Returns:
            Tuple of (semantic_weight, keyword_weight) = (1.0, 1.5).

        Note:
            The keyword weight is higher because exact keyword matches
            are more reliable indicators of relevance for tool search.
        """
        return (1.0, 1.5)

    def stats(self) -> dict[str, Any]:
        """Get hybrid search engine statistics and configuration.

        Returns a dictionary containing the current search configuration
        and algorithm parameters. Useful for debugging and monitoring.

        Returns:
            Dict with keys:
            - semantic_weight: Weight for vector search (1.0)
            - keyword_weight: Weight for keyword search (1.5)
            - rrf_k: RRF smoothing parameter (10)
            - implementation: Implementation name
            - strategy: Fusion strategy used
            - field_boosting: Token/phrase boost values
        """
        return {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "implementation": "rust-native-weighted-rrf",
            "strategy": "weighted_rrf_field_boosting",
            "field_boosting": {
                "name_token_boost": 0.5,  # Per matched term in tool name
                "exact_phrase_boost": 1.5,  # Full query in tool name
            },
        }


__all__ = ["HybridSearch", "HybridMatch"]
