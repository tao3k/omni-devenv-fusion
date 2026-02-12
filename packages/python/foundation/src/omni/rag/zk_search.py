"""
zk_search.py - Reasoning-based Retrieval using ZK Bidirectional Links

Implements PageIndex-style reasoning loop for high-precision retrieval:
1. Load ZK tree structure (wikilinks hierarchy)
2. LLM infers which sections/notes are relevant
3. Fetch content via bidirectional links
4. Iterate until context is sufficient

Usage:
    from omni.rag.zk_search import ZkReasoningSearcher, ZkSearchResult

    searcher = ZkReasoningSearcher(notebook_dir="assets/knowledge")
    results = await searcher.search("agent skills progressive disclosure", max_iterations=3)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .zk_integration import ZkClient, ZkNote

logger = logging.getLogger(__name__)


@dataclass
class ZkSearchResult:
    """Search result from ZK reasoning-based retrieval."""

    note: ZkNote
    relevance_score: float  # 0.0 to 1.0
    source: str  # "direct", "linked_by", "related", "recursive"
    distance: int  # Link distance from original query
    reasoning: str  # Why this note was selected


@dataclass
class ZkSearchConfig:
    """Configuration for ZK reasoning search."""

    # Search strategy
    max_iterations: int = 3  # Reasoning loop iterations
    max_distance: int = 3  # Maximum link distance
    max_notes_per_iteration: int = 10

    # Weights for scoring
    direct_match_weight: float = 1.0
    linked_by_weight: float = 0.8
    related_weight: float = 0.6
    recursive_weight: float = 0.4

    # Minimum score threshold
    min_score: float = 0.3

    # Whether to include vector search fallback
    use_vector_fallback: bool = True


class ZkReasoningSearcher:
    """Reasoning-based search using ZK bidirectional links.

    Mimics PageIndex's reasoning loop:
    1. Load ZK structure (wikilinks + tags)
    2. LLM infers relevant notes
    3. Traverse bidirectional links
    4. Iterate until sufficient context
    """

    def __init__(
        self,
        notebook_dir: str | Path | None = None,
        config: ZkSearchConfig | None = None,
    ):
        """Initialize the reasoning searcher.

        Args:
            notebook_dir: Directory containing .zk/zk.toml. If None, uses CWD.
                          Note: ZK config is typically at project root (.zk/)
                          even if notes are in a subdirectory like assets/knowledge.
        """
        # ZK expects notebook_dir to be where .zk folder exists
        # If not specified, use current working directory
        self.notebook_dir = Path(notebook_dir) if notebook_dir else Path.cwd()
        self.config = config or ZkSearchConfig()
        self.zk_client = ZkClient(self.notebook_dir)

    async def search(
        self,
        query: str,
        context: str | None = None,
        max_results: int = 20,
    ) -> list[ZkSearchResult]:
        """Perform reasoning-based search using ZK links.

        Args:
            query: Search query.
            context: Additional context (e.g., chat history).
            max_results: Maximum results to return.

        Returns:
            List of search results with relevance scores.
        """
        results: list[ZkSearchResult] = []

        try:
            # Step 1: Direct keyword search (like reading ToC)
            direct_results = await self._search_direct(query, max_results)
            results.extend(direct_results)

            # Step 2: Find starting points for link traversal
            starting_points = self._get_starting_points(direct_results)

            # Step 3: Reasoning loop - traverse links iteratively
            iteration = 0
            while iteration < self.config.max_iterations and len(results) < max_results * 2:
                iteration += 1

                # Get linked notes from starting points
                linked_results = await self._traverse_links(
                    starting_points,
                    iteration,
                    max_per_point=max(
                        5, self.config.max_notes_per_iteration // len(starting_points)
                    )
                    if starting_points
                    else self.config.max_notes_per_iteration,
                )

                # Filter by score threshold
                linked_results = [
                    r for r in linked_results if r.relevance_score >= self.config.min_score
                ]

                # Add new results (avoid duplicates)
                existing_ids = {r.note.filename_stem for r in results}
                new_results = [
                    r for r in linked_results if r.note.filename_stem not in existing_ids
                ]

                if not new_results:
                    break

                results.extend(new_results)

                # Update starting points for next iteration
                starting_points = self._get_starting_points(new_results)

            # Step 4: Score and rank results
            scored_results = self._rank_results(results, query, context)

            # Step 5: Return top-k results
            return scored_results[:max_results]

        except Exception as e:
            logger.error(f"ZK reasoning search failed: {e}")
            return []

    async def _search_direct(
        self,
        query: str,
        limit: int,
    ) -> list[ZkSearchResult]:
        """Step 1: Direct keyword search (like PageIndex reading ToC)."""
        results = []

        # Use zk list with match
        notes = await self.zk_client.list_notes(
            match=query,
            limit=limit * 2,  # Get more to filter later
        )

        for note in notes:
            # Calculate relevance based on title match, tag match, etc.
            score = self._calculate_direct_score(query, note)
            results.append(
                ZkSearchResult(
                    note=note,
                    relevance_score=score,
                    source="direct",
                    distance=0,
                    reasoning=f"Direct match for '{query}' in title/tags",
                )
            )

        # Also search by tags
        tags = self._extract_tags_from_query(query)
        for tag in tags:
            tag_notes = await self.zk_client.list_notes(tags=[tag], limit=limit)
            for note in tag_notes:
                # Check if already added
                if any(r.note.filename_stem == note.filename_stem for r in results):
                    continue

                score = self._calculate_direct_score(query, note, tag_match=True)
                results.append(
                    ZkSearchResult(
                        note=note,
                        relevance_score=score,
                        source="direct",
                        distance=0,
                        reasoning=f"Tag match for '#{tag}'",
                    )
                )

        return results

    def _get_starting_points(
        self,
        results: list[ZkSearchResult],
    ) -> list[str]:
        """Get note IDs to start link traversal from."""
        # Sort by score and take top results
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        return [r.note.filename_stem for r in sorted_results[:5]]

    async def _traverse_links(
        self,
        note_ids: list[str],
        iteration: int,
        max_per_point: int,
    ) -> list[ZkSearchResult]:
        """Step 2: Traverse bidirectional links (PageIndex reasoning loop)."""
        results = []

        for note_id in note_ids:
            if len(results) >= max_per_point * len(note_ids):
                break

            # Get notes linked BY this note (outgoing links - these link TO note_id)
            linked_by = await self.zk_client.list_notes(
                linked_by=[note_id],
                limit=max_per_point,
            )

            for note in linked_by:
                distance = iteration  # Iteration = link distance
                score = self._calculate_link_score(note, iteration)
                source = "linked_by" if iteration == 1 else "recursive"

                results.append(
                    ZkSearchResult(
                        note=note,
                        relevance_score=score,
                        source=source,
                        distance=distance,
                        reasoning=f"Linked from iteration {iteration}",
                    )
                )

            # Get notes LINKING TO this note (incoming links - these are linked FROM note_id)
            linking_to = await self.zk_client.list_notes(
                link_to=[note_id],
                limit=max_per_point,
            )

            for note in linking_to:
                distance = iteration
                score = self._calculate_link_score(note, iteration)
                source = "linked_by" if iteration == 1 else "recursive"

                results.append(
                    ZkSearchResult(
                        note=note,
                        relevance_score=score,
                        source=source,
                        distance=distance,
                        reasoning=f"Linked to in iteration {iteration}",
                    )
                )

        return results

    def _rank_results(
        self,
        results: list[ZkSearchResult],
        query: str,
        context: str | None = None,
    ) -> list[ZkSearchResult]:
        """Step 3: Rank and score final results."""
        # Apply distance penalty
        for result in results:
            # Higher distance = lower score
            distance_penalty = max(0, 1.0 - (result.distance * 0.1))
            result.relevance_score *= distance_penalty

        # Sort by final score
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)

    def _calculate_direct_score(self, query: str, note: ZkNote, tag_match: bool = False) -> float:
        """Calculate relevance score for direct match."""
        query_lower = query.lower()
        score = 0.0

        # Title match (highest weight)
        if note.title.lower() == query_lower:
            score += 1.0
        elif query_lower in note.title.lower():
            score += 0.8
        elif any(word in note.title.lower() for word in query_lower.split()):
            score += 0.5

        # Tag match
        if tag_match:
            score += 0.7

        # Lead/body match (lower weight)
        if note.lead and query_lower in note.lead.lower():
            score += 0.3
        if note.raw_content and query_lower in note.raw_content.lower():
            score += 0.2

        return min(1.0, score)

    def _calculate_link_score(self, note: ZkNote, iteration: int) -> float:
        """Calculate relevance score for linked notes."""
        # Base score decreases with iteration
        base_score = max(0.3, 1.0 - (iteration * 0.15))

        # Boost if note has tags (likely relevant)
        if note.tags:
            base_score += 0.1

        # Boost if note has substantial content
        if note.raw_content and len(note.raw_content) > 200:
            base_score += 0.05

        return min(1.0, base_score)

    def _extract_tags_from_query(self, query: str) -> list[str]:
        """Extract potential tags from query."""
        import re

        # Look for #tag patterns in query
        tags = re.findall(r"#(\w+)", query)
        return tags

    async def get_toc_for_context(self) -> str:
        """Get Table of Contents (all notes) for embedding in LLM context.

        Returns:
            JSON string representing the document tree structure.
        """
        # Always use JSON format for parsing
        notes = await self.zk_client.list_notes(limit=1000)

        # Build tree structure
        toc = {
            "notes": [
                {
                    "id": n.filename_stem,
                    "title": n.title,
                    "tags": n.tags,
                    "lead": n.lead[:100] if n.lead else "",
                }
                for n in notes
            ],
            "total": len(notes),
        }

        return json.dumps(toc, indent=2)


class ZkHybridSearcher:
    """Hybrid search combining ZK reasoning + Vector search.

    TIER 1: ZK search (high precision)
    TIER 2: Vector search (fallback for unknown topics)
    """

    def __init__(
        self,
        notebook_dir: str | Path | None = None,
        zk_config: ZkSearchConfig | None = None,
        vector_search_func: callable | None = None,
    ):
        """Initialize hybrid searcher.

        Args:
            notebook_dir: ZK notebook directory.
            zk_config: ZK search configuration.
            vector_search_func: Optional function for vector search fallback.
        """
        self.notebook_dir = notebook_dir
        self.zk_searcher = ZkReasoningSearcher(notebook_dir, zk_config)
        self.vector_search_func = vector_search_func

    async def search(
        self,
        query: str,
        context: str | None = None,
        max_results: int = 20,
        use_hybrid: bool = True,
    ) -> dict[str, Any]:
        """Perform hybrid search.

        Args:
            query: Search query.
            context: Additional context.
            max_results: Maximum results.
            use_hybrid: If False, use only ZK search.

        Returns:
            Dict with 'zk_results', 'vector_results', 'merged_results'.
        """
        zk_results: list[ZkSearchResult] = []
        vector_results: list[dict] = []
        merged_results: list[dict] = []

        # TIER 1: ZK Search (high precision)
        try:
            zk_results = await self.zk_searcher.search(query, context, max_results)
            logger.info(f"ZK search returned {len(zk_results)} results")
        except Exception as e:
            logger.error(f"ZK search failed: {e}")

        # TIER 2: Vector Search (fallback)
        if self.vector_search_func and self.zk_searcher.config.use_vector_fallback:
            try:
                vector_results = await self.vector_search_func(query, limit=max_results)
                logger.info(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.error(f"Vector search failed: {e}")

        # Merge results if using hybrid
        if use_hybrid and (zk_results or vector_results):
            merged_results = self._merge_results(zk_results, vector_results, query)
        elif zk_results:
            merged_results = [
                {
                    "note": r.note,
                    "score": r.relevance_score,
                    "source": "zk",
                    "reasoning": r.reasoning,
                }
                for r in zk_results
            ]
        elif vector_results:
            merged_results = vector_results

        return {
            "zk_results": [
                {
                    "note": r.note.to_dict(),
                    "score": r.relevance_score,
                    "source": r.source,
                    "distance": r.distance,
                    "reasoning": r.reasoning,
                }
                for r in zk_results
            ],
            "vector_results": vector_results,
            "merged_results": merged_results,
            "total_zk": len(zk_results),
            "total_vector": len(vector_results),
            "total_merged": len(merged_results),
        }

    def _merge_results(
        self,
        zk_results: list[ZkSearchResult],
        vector_results: list[dict],
        query: str,
    ) -> list[dict]:
        """Merge ZK and vector results with ranking."""
        merged: dict[str, dict] = {}

        # Add ZK results
        for r in zk_results:
            key = r.note.filename_stem
            merged[key] = {
                "note": r.note,
                "score": r.relevance_score * 1.5,  # ZK boost for precision
                "source": "zk",
                "reasoning": r.reasoning,
            }

        # Add vector results
        for v in vector_results:
            key = v.get("id") or v.get("note_id") or v.get("filename_stem")
            if not key:
                continue

            vector_score = v.get("score", 0.5)

            if key in merged:
                # Average with existing score (both ZK and vector found it)
                merged[key]["score"] = (merged[key]["score"] + vector_score) / 2
                merged[key]["source"] = "hybrid"
            else:
                merged[key] = {
                    "note": v.get("note"),
                    "score": vector_score,
                    "source": "vector",
                    "reasoning": f"Vector similarity match for '{query}'",
                }

        # Sort by score and return
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results


# ============================================================================
# Convenience Functions
# ============================================================================


def get_zk_searcher(
    notebook_dir: str | Path | None = None,
    config: ZkSearchConfig | None = None,
) -> ZkReasoningSearcher:
    """Get a ZK reasoning searcher instance."""
    return ZkReasoningSearcher(notebook_dir, config)


def get_zk_hybrid_searcher(
    notebook_dir: str | Path | None = None,
    vector_search_func: callable | None = None,
) -> ZkHybridSearcher:
    """Get a ZK hybrid searcher instance."""
    return ZkHybridSearcher(notebook_dir, vector_search_func=vector_search_func)


__all__ = [
    "ZkSearchResult",
    "ZkSearchConfig",
    "ZkReasoningSearcher",
    "ZkHybridSearcher",
    "get_zk_searcher",
    "get_zk_hybrid_searcher",
]
