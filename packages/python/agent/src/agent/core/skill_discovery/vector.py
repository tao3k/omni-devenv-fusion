"""
src/agent/core/skill_discovery/vector.py
 Vector-Enhanced Skill Discovery (ChromaDB)
 Cognitive Indexing & Adaptive Routing
 Self-Evolving Feedback Loop (Harvester Integration)

Semantic Skill Discovery using ChromaDB for intelligent matching.
Features:
- Semantic similarity search
- Hybrid search: vector + keyword boosting (Base + Boost model)
- Fuzzy keyword matching (substring, stemming)
- Sigmoid score calibration for better distribution
-  Feedback-based reinforcement learning
"""

from __future__ import annotations

from typing import Any

import structlog

from .indexing import SKILL_REGISTRY_COLLECTION

logger = structlog.get_logger(__name__)

# Hybrid search configuration
HYBRID_RECALL_FACTOR = 4  # Multiply limit by this factor for initial recall

# Scoring calibration
KEYWORD_BONUS = 0.15  # Bonus for keyword match (additive, not multiplicative)
MIN_CONFIDENCE = 0.3  # Minimum score floor
MAX_CONFIDENCE = 0.95  # Maximum score ceiling (leave room for "certain")

# Verb-priority boost - core action verbs get extra weight
CORE_ACTION_VERBS = {
    "commit",
    "push",
    "pull",
    "merge",
    "deploy",
    "build",
    "test",
    "run",
    "create",
    "delete",
    "update",
    "write",
    "read",
    "search",
    "find",
    "install",
    "remove",
    "check",
    "validate",
    "lint",
    "format",
    "save",
    "load",
    "fetch",
    "sync",
    "rebase",
    "checkout",
    "stash",
}
VERB_PRIORITY_BONUS = 0.10  # Extra bonus when matching core verbs


def _get_feedback_boost_safe(query: str, skill_id: str) -> float:
    """
     Safely get feedback boost without crashing on import errors.

    This function wraps the Harvester's get_feedback_boost to handle
    cases where the module hasn't been initialized yet.

    Args:
        query: The user query
        skill_id: The skill to check

    Returns:
        Score adjustment from feedback (-0.3 to +0.3), or 0.0 if unavailable
    """
    try:
        from agent.capabilities.learning.harvester import get_feedback_boost

        return get_feedback_boost(query, skill_id)
    except Exception:
        # Silently return 0 if feedback system is not available
        return 0.0


def _sigmoid_calibration(score: float) -> float:
    """
     Apply sigmoid calibration to stretch score distribution.

    This helps if the embedding model outputs compressed scores.
    Sigmoid: f(x) = 1 / (1 + exp(-k*(x - offset)))

    Args:
        score: Raw score (0.0 - 1.0)

    Returns:
        Calibrated score (0.0 - 1.0)
    """
    import math

    # Sigmoid with offset at 0.5, steepness of 6
    k = 6.0
    offset = 0.5
    calibrated = 1.0 / (1.0 + math.exp(-k * (score - offset)))
    return max(0.0, min(1.0, calibrated))


def _fuzzy_keyword_match(query_tokens: set[str], skill_keywords: set[str]) -> tuple[int, bool]:
    """
     Fuzzy keyword matching with verb priority detection.

    Matches considering:
    1. Exact match (highest priority)
    2. Substring match (query contains keyword or vice versa)
    3. Stemming approximation (removes common suffixes like 's', 'ing', 'ed')

     Also detects if a core action verb was matched.

    Args:
        query_tokens: Tokenized user query
        skill_keywords: Skill's routing keywords

    Returns:
        Tuple of (match_count, verb_matched):
        - match_count: Number of matching keywords (capped at 3)
        - verb_matched: True if a core action verb was matched
    """
    matches = 0
    max_matches = 3
    verb_matched = False

    # Build stemmed versions for both
    def stem_word(word: str) -> str:
        """Simple stemming: remove common suffixes."""
        word = word.lower().strip()
        # Remove common suffixes
        for suffix in ["ing", "s", "es", "ed", "'s"]:
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                return word[: -len(suffix)]
        return word

    stemmed_query = {stem_word(t) for t in query_tokens if len(t) > 2}
    stemmed_keywords = {stem_word(k) for k in skill_keywords if len(k) > 2}

    for q_token in query_tokens:
        q_lower = q_token.lower()

        for kw in skill_keywords:
            kw_lower = kw.lower().strip()
            matched = False

            # 1. Exact match
            if q_lower == kw_lower:
                matched = True

            # 2. Substring match (keyword in query or query in keyword)
            # e.g., "tests" matches "test", "commit" matches "git-commit"
            elif kw_lower in q_lower or q_lower in kw_lower:
                matched = True

            # 3. Stemmed match
            else:
                q_stemmed = stem_word(q_lower)
                kw_stemmed = stem_word(kw_lower)
                if q_stemmed == kw_stemmed and q_stemmed:
                    matched = True

            if matched:
                matches += 1
                # Check if the matched token is a core verb
                if q_lower in CORE_ACTION_VERBS or stem_word(q_lower) in CORE_ACTION_VERBS:
                    verb_matched = True
                break  # Move to next query token

        if matches >= max_matches:
            break

    return min(matches, max_matches), verb_matched


class VectorSkillDiscovery:
    """
    Semantic Skill Discovery using ChromaDB.

    Provides vector-based semantic search over skill definitions,
    enabling fuzzy matching even when exact keywords don't match.

    Features:
    - Semantic similarity search (e.g., "draw chart" -> "visualization")
    - Hybrid search: vector + keyword fallback
    - Fuzzy keyword matching (substring, stemming)
    - Sigmoid score calibration
    - Persistent index across sessions
    - Incremental updates for new skills
    """

    COLLECTION_NAME = SKILL_REGISTRY_COLLECTION

    def __init__(self):
        """Initialize vector-based skill discovery."""
        self._vm: Any = None

    def _get_vector_memory(self) -> Any:
        """Get VectorMemory instance lazily."""
        if self._vm is None:
            from agent.core.vector_store import get_vector_memory

            self._vm = get_vector_memory()
        return self._vm

    async def search(
        self, query: str, limit: int = 5, installed_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Search skills using hybrid search (vector + keyword boosting).

         Combines vector similarity with fuzzy keyword matching.
         Uses "Base + Boost" scoring model (not weighted average).

        Scoring Formula:
            base_score = vector_similarity (0.0 - 1.0)
            keyword_bonus = min(matches, 3) * KEYWORD_BONUS
            final_score = sigmoid(base_score) + keyword_bonus
            final_score = clamp(MIN_CONFIDENCE, MAX_CONFIDENCE)

        By default, only returns installed (local) skills.
        Set installed_only=False to search remote skills from known_skills.json.

        Args:
            query: Search query (natural language)
            limit: Maximum number of results
            installed_only: Only return installed (local) skills (default: True)

        Returns:
            List of matching skill dicts with metadata and scores
        """
        from typing import Dict, Optional

        vm = self._get_vector_memory()

        # Build filter for installed skills
        where_filter: Optional[Dict[str, str]] = None
        if installed_only:
            where_filter = {"installed": "true"}

        try:
            # Expand recall range for better re-ranking
            recall_limit = limit * HYBRID_RECALL_FACTOR
            raw_results = await vm.search(
                query=query,
                n_results=recall_limit,
                collection=self.COLLECTION_NAME,
                where_filter=where_filter,
            )

            if not raw_results:
                return []

            # Tokenize query for keyword matching
            query_tokens = set(query.lower().split())

            # Process and re-rank results using hybrid scoring
            processed_skills = []
            for res in raw_results:
                # Convert distance to vector similarity score (0.0 - 1.0)
                raw_vector_score = max(0.0, min(1.0, 1.0 - res.distance))

                # Apply sigmoid calibration to stretch scores
                vector_score = _sigmoid_calibration(raw_vector_score)

                # Fuzzy keyword matching
                skill_keywords_str = res.metadata.get("keywords", "")
                skill_keywords = set(
                    kw.strip().lower() for kw in skill_keywords_str.split(",") if kw.strip()
                )

                # Count fuzzy matches with verb detection
                keyword_matches, verb_matched = _fuzzy_keyword_match(query_tokens, skill_keywords)
                keyword_bonus = keyword_matches * KEYWORD_BONUS

                # Extra bonus for matching core action verbs
                verb_bonus = VERB_PRIORITY_BONUS if verb_matched else 0.0

                # Feedback-based reinforcement learning
                # Get learned boost/penalty from past user interactions
                skill_id = res.metadata.get("id", res.id)
                feedback_bonus = _get_feedback_boost_safe(query, skill_id)

                # Base + Boost scoring model
                # Don't penalize good vector matches; add bonus for keyword hits
                final_score = vector_score + keyword_bonus + verb_bonus + feedback_bonus

                # Clamp to valid range
                final_score = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, final_score))

                processed_skills.append(
                    {
                        "id": skill_id,
                        "name": res.metadata.get("name", res.metadata.get("id", "")),
                        "description": res.content[:200] if res.content else "",
                        "keywords": res.metadata.get("keywords", "").split(","),
                        "score": round(final_score, 3),
                        "raw_vector_score": round(raw_vector_score, 3),
                        "calibrated_vector": round(vector_score, 3),
                        "keyword_matches": keyword_matches,
                        "keyword_bonus": round(keyword_bonus, 2),
                        "verb_matched": verb_matched,
                        "verb_bonus": round(verb_bonus, 2),
                        "feedback_bonus": round(feedback_bonus, 2),
                        "installed": res.metadata.get("installed", "false") == "true",
                        "type": res.metadata.get("type", "local"),
                    }
                )

            # Re-rank by final hybrid score
            processed_skills.sort(key=lambda x: x["score"], reverse=True)

            # Apply limit
            skills = processed_skills[:limit]

            logger.info(
                "Hybrid skill search completed",
                query=query[:50],
                results=len(skills),
                method="hybrid_base_plus_boost",
            )
            return skills

        except Exception as e:
            logger.error("Hybrid skill search failed", error=str(e))
            return []

    async def suggest_for_query(self, query: str, limit: int = 5) -> dict[str, Any]:
        """
        Analyze a query and suggest skills using semantic search.

        Args:
            query: User's request/query
            limit: Maximum suggestions

        Returns:
            Dict with suggestions, method, and reasoning
        """
        suggestions = await self.search(query, limit=limit)

        return {
            "query": query,
            "suggestions": suggestions,
            "count": len(suggestions),
            "method": "hybrid_vector_keyword",
            "ready_to_install": [s["id"] for s in suggestions if not s.get("installed", True)],
        }

    async def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the skill index."""
        vm = self._get_vector_memory()
        count = await vm.count(collection=self.COLLECTION_NAME)
        collections = await vm.list_collections()

        return {
            "collection": self.COLLECTION_NAME,
            "skill_count": count,
            "available_collections": collections,
        }


# Convenience functions
async def vector_search_skills(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Quick semantic search for skills.

    Args:
        query: Search query
        limit: Max results

    Returns:
        List of matching skills with scores
    """
    discovery = VectorSkillDiscovery()
    return await discovery.search(query, limit=limit)


async def vector_suggest_for_task(task: str) -> dict[str, Any]:
    """
    Get semantic skill suggestions for a task.

    Args:
        task: Task description

    Returns:
        Suggestion dict with matching skills
    """
    discovery = VectorSkillDiscovery()
    return await discovery.suggest_for_query(task)


__all__ = [
    "VectorSkillDiscovery",
    "vector_search_skills",
    "vector_suggest_for_task",
    "_sigmoid_calibration",
    "_fuzzy_keyword_match",
]
