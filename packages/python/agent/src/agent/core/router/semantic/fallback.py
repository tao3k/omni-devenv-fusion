# agent/core/router/semantic/fallback.py
"""
Vector Fallback - Virtual Loading via Vector Discovery.

Provides fallback routing when LLM routing fails or is weak.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.core.router.models import RoutingResult

# Adaptive confidence configuration
CONFIDENCE_HIGH_GAP = 0.15  # Gap > 15% = High confidence boost
CONFIDENCE_LOW_GAP = 0.05  # Gap < 5% = Low confidence penalty
CONFIDENCE_MAX_BOOST = 1.15  # Max boost multiplier for high distinctiveness
CONFIDENCE_MAX_PENALTY = 0.85  # Max penalty multiplier for ambiguity

# Lazy logger
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


async def try_vector_fallback(
    query: str,
    result: "RoutingResult",
    vector_discovery: Any,
) -> None:
    """
    Search local skills via vector store for better routing.
    Adaptive Confidence based on Score Gap.

    This is the "Cold Path" - used when LLM routing fails or is weak.
    1. First search LOCAL (installed) skills
    2. If no local skills found, search REMOTE skills and return suggestions
    3. Calculate adaptive confidence based on score gap

    Args:
        query: The user query
        result: RoutingResult to modify in-place
        vector_discovery: VectorSkillDiscovery instance
    """
    try:
        # 1. Search local skills first (local_only=True by default)
        suggestions = await vector_discovery.search(
            query=query,
            limit=3,
            local_only=True,  # Only local skills
        )

        # Filter out already selected skills
        loaded_skills = set(result.selected_skills)
        new_candidates = [s for s in suggestions if s.get("id") not in loaded_skills]

        # 2. If no local skills found, search remote skills for suggestions
        if not new_candidates:
            # Search remote skills (Auto-trigger skill.suggest logic)
            remote_suggestions = await vector_discovery.search(
                query=query,
                limit=5,
                local_only=False,  # Search all skills (remote too)
            )

            if remote_suggestions:
                # Add remote suggestions to result
                for skill in remote_suggestions:
                    if skill.get("id") not in loaded_skills:
                        result.remote_suggestions.append(
                            {
                                "id": skill.get("id"),
                                "name": skill.get("name"),
                                "description": skill.get("description", ""),
                                "keywords": skill.get("keywords", []),
                                "score": skill.get("score", 0.0),
                                "installed": skill.get("installed", False),
                                "url": skill.get("url", ""),
                            }
                        )

                result.reasoning += (
                    f" [Skill Suggestion] No local skills found. "
                    f"Found {len(remote_suggestions)} remote skill(s) that may help."
                )
                result.confidence = 0.3  # Low confidence, but providing suggestions

                _get_logger().info(
                    "Auto-triggered skill suggestion",
                    query=query[:50],
                    suggestions=[s.get("id") for s in remote_suggestions],
                )
                return

        if not new_candidates:
            return

        # Found local skills!
        top_skill = new_candidates[0]
        suggested_ids = [s.get("id") for s in new_candidates]

        # Add newly discovered skills to selected_skills
        for skill_id in suggested_ids:
            if skill_id not in result.selected_skills:
                result.selected_skills.append(skill_id)

        # Update result with suggestions
        result.suggested_skills = suggested_ids

        # Build reasoning with boost details
        reasoning_parts = [f"Found relevant local skills: {', '.join(suggested_ids)}."]

        # Check for feedback influence
        feedback_bonus = top_skill.get("feedback_bonus", 0.0)
        keyword_boost = top_skill.get("keyword_bonus", 0.0)
        verb_matched = top_skill.get("verb_matched", False)

        if feedback_bonus > 0:
            reasoning_parts.append(f"(Reinforced by past success +{feedback_bonus:.2f})")
        elif feedback_bonus < 0:
            reasoning_parts.append(f"(Penalized by past rejection {feedback_bonus:.2f})")

        if keyword_boost > 0:
            if verb_matched:
                reasoning_parts.append(f"(Keyword match +{keyword_boost:.2f} with verb priority)")
            else:
                reasoning_parts.append(f"(Keyword match +{keyword_boost:.2f})")

        result.reasoning += " [Vector Fallback] " + " ".join(reasoning_parts)

        # Adaptive Confidence based on Score Gap
        _apply_adaptive_confidence(query, result, new_candidates)

        _get_logger().info(
            "Vector fallback triggered",
            query=query[:50],
            selected_skills=result.selected_skills,
            suggestions=suggested_ids,
            confidence=result.confidence,
        )

    except Exception as e:
        _get_logger().warning("Vector fallback failed", error=str(e))


def _apply_adaptive_confidence(
    query: str,
    result: "RoutingResult",
    candidates: list[dict],
) -> None:
    """
    Apply adaptive confidence based on score gap between top candidates.

    Args:
        query: The user query (for logging)
        result: RoutingResult to modify in-place
        candidates: List of candidate skills with scores
    """
    if len(candidates) >= 2:
        top_score = candidates[0].get("score", 0.0)
        second_score = candidates[1].get("score", 0.0)
        score_gap = top_score - second_score

        # Get raw score and keyword boost for debugging
        raw_vector = candidates[0].get("raw_vector_score", top_score)
        keyword_boost = candidates[0].get("keyword_boost", 0.0)

        if score_gap > CONFIDENCE_HIGH_GAP:
            # High distinctiveness: boost confidence
            boosted = min(CONFIDENCE_MAX_BOOST, 1.0 + (score_gap * 0.5))
            result.confidence = min(0.95, top_score * boosted)
            result.reasoning += (
                f" [High Confidence] Score gap ({score_gap:.2f}) indicates strong match."
            )
            _get_logger().info(
                "Adaptive confidence: high distinctiveness",
                query=query[:50],
                top_score=top_score,
                second_score=second_score,
                gap=score_gap,
                final_confidence=result.confidence,
            )
        elif score_gap < CONFIDENCE_LOW_GAP:
            # Ambiguous match: penalize confidence
            penalized = max(CONFIDENCE_MAX_PENALTY, 1.0 - (CONFIDENCE_LOW_GAP - score_gap))
            result.confidence = max(0.3, top_score * penalized)
            result.reasoning += (
                f" [Low Confidence] Score gap ({score_gap:.2f}) indicates ambiguity."
            )
            _get_logger().info(
                "Adaptive confidence: ambiguous match",
                query=query[:50],
                top_score=top_score,
                second_score=second_score,
                gap=score_gap,
                final_confidence=result.confidence,
            )
        else:
            # Moderate gap: use base score
            result.confidence = top_score
            result.reasoning += f" [Moderate Confidence] Score gap: {score_gap:.2f}."

        # Log detailed scoring info
        _get_logger().debug(
            "Vector search scoring details",
            query=query[:50],
            top_skill=candidates[0].get("id"),
            top_score=top_score,
            raw_vector_score=raw_vector,
            keyword_boost=keyword_boost,
            second_score=second_score,
            score_gap=score_gap,
        )
    else:
        # Only one result - use its score as base confidence
        result.confidence = candidates[0].get("score", 0.7)
        result.reasoning += " [Single Result] Only one relevant skill found."
