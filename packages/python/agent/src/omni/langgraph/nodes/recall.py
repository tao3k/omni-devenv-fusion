"""
omni/langgraph/nodes/recall.py - Semantic Recall Node

Implements the "Recall" node for retrieving similar historical experiences
from LanceDB checkpoints during Agent self-healing workflows.

Flow:
    Reflect (failed) → Recall → Plan (with injected wisdom)

Usage:
    from omni.langgraph.nodes.recall import recall_node

    graph.add_node("recall", partial(recall_node, checkpointer=checkpointer))
"""

from __future__ import annotations

import json
from typing import Any, TypedDict, Literal
from structlog import get_logger

from omni.langgraph.state import GraphState


# Type definitions for recall results
class RecallResult(TypedDict):
    """Result from recall_node."""

    content: dict[str, Any]  # The state content
    metadata: dict[str, Any]  # Checkpoint metadata
    distance: float  # Similarity score (lower is better)


# Lazy import for embedding service
_cached_embedder: Any | None = None


def _get_embedder():
    """Get the embedding service lazily."""
    global _cached_embedder
    if _cached_embedder is None:
        try:
            from omni.foundation.services.embedding import EmbeddingService

            _cached_embedder = EmbeddingService()
        except ImportError:
            _cached_embedder = None
    return _cached_embedder


logger = get_logger("omni.langgraph.nodes.recall")


def should_recall(state: GraphState) -> Literal["recall", "end"]:
    """
    Determine whether to trigger recall based on state.

    Triggers recall when:
    1. Reflection was not approved
    2. There was an error
    3. Confidence is low

    Args:
        state: Current graph state

    Returns:
        "recall" to trigger recall, "end" to terminate
    """
    workflow = state.get("workflow_state", {})
    error_count = state.get("error_count", 0)
    approved = workflow.get("approved", False)

    # If already approved, no need to recall
    if approved:
        return "end"

    # If too many errors, give up
    if error_count >= 3:
        logger.warn("too_many_errors_giving_up", error_count=error_count)
        return "end"

    # If reflection failed or there was an error, recall experience
    last_result = workflow.get("last_result", {})
    has_error = last_result.get("error") is not None
    confidence = workflow.get("confidence", 1.0)

    if not approved or has_error or confidence < 0.7:
        logger.info(
            "triggering_recall",
            approved=approved,
            has_error=has_error,
            confidence=confidence,
        )
        return "recall"

    return "end"


async def recall_node(
    state: GraphState,
    checkpointer: Any,  # LanceCheckpointer
    top_k: int = 3,
    min_similarity: float | None = None,  # Max distance threshold (None = no filter)
) -> dict[str, Any]:
    """
    Recall Node: Retrieve similar historical experiences from checkpoint store.

    This node is triggered after a failed reflection or error, searching for
    similar past experiences to help the agent "learn from history".

    Args:
        state: Current graph state
        checkpointer: LanceCheckpointer instance
        top_k: Number of similar experiences to retrieve
        min_similarity: Maximum distance threshold (lower = more similar)

    Returns:
        Dict with:
        - recalled_lessons: List of formatted lesson strings
        - recalled_experiences: List of raw experience dicts
    """
    log = logger.bind(node="recall")

    # 1. Build the query text from current state
    workflow = state.get("workflow_state", {})
    last_error = workflow.get("last_result", {}).get("error")
    current_plan = state.get("current_plan", "")

    # Priority: error > plan > workflow state
    if last_error:
        query_text = f"Error resolution: {last_error}"
        log = log.bind(query_type="error", error=last_error[:100])
    else:
        query_text = f"Plan: {current_plan}"
        log = log.bind(query_type="plan", plan=current_plan[:100])

    log.info("recalling_experience", query=query_text[:100])

    try:
        # 2. Get embedding for the query
        embedder = _get_embedder()
        if embedder is None:
            log.warn("no_embedder_service_fallback_to_history")
            # Fallback: just get recent history
            history = checkpointer.get_history(
                thread_id=None,
                limit=top_k,
            )
            return _format_recall_results(history, "history_fallback")

        # 3. Compute embedding vector (sync call)
        # embed() returns list[list[float]], extract first element
        query_vector = embedder.embed(query_text)[0]
        log.debug("embedding_computed", vector_dim=len(query_vector))

        # 4. Search for similar checkpoints
        results: list[RecallResult] = checkpointer.search_similar(
            query_vector=query_vector,
            thread_id=None,  # Search across all sessions for cross-session learning
            limit=top_k,
            filter_metadata={"success": True},  # Prefer successful experiences
        )

        log.info("search_completed", results_count=len(results))

        # 5. Filter by similarity and format (if threshold specified)
        if min_similarity is not None:
            threshold = float(min_similarity)  # type: ignore[arg-type]
            filtered = [r for r in results if r["distance"] < threshold]
            log.debug("filtered_by_similarity", after_filter=len(filtered), threshold=threshold)
        else:
            filtered = results
            log.debug("no_similarity_filter", results_count=len(filtered))

        # 6. Format lessons for the planner
        lessons = _format_lessons(filtered)
        experiences = [r["content"] for r in filtered]

        if not lessons:
            log.info("no_relevant_experience_found")
            return {
                "workflow_state": {
                    **workflow,
                    "recalled_lessons": [],
                    "recalled_experiences": [],
                }
            }

        log.info(
            "experience_recalled",
            lessons_count=len(lessons),
            best_distance=filtered[0]["distance"] if filtered else None,
        )

        # 7. Return with injected context
        return {
            "workflow_state": {
                **workflow,
                "recalled_lessons": lessons,
                "recalled_experiences": experiences,
            }
        }

    except Exception as e:
        log.error("recall_failed", error=str(e), error_type=type(e).__name__)
        # Don't fail the workflow, just return empty recall
        return {
            "workflow_state": {
                **workflow,
                "recalled_lessons": [],
                "recalled_experiences": [],
            }
        }


def _format_lessons(experiences: list[RecallResult]) -> list[str]:
    """
    Format experiences into readable lesson strings for the planner.

    Args:
        experiences: List of recall results

    Returns:
        List of formatted lesson strings
    """
    lessons = []
    for i, exp in enumerate(experiences):
        content = exp["content"]
        metadata = exp["metadata"]
        distance = exp["distance"]

        # Extract key information
        plan = content.get("current_plan", "Unknown plan")
        step = content.get("step", 0)
        thread_id = metadata.get("thread_id", "unknown")

        # Format as a lesson
        lesson = (
            f"[Experience #{i + 1}] (similarity: {distance:.2f}, from {thread_id}):\n"
            f"  Plan: {plan[:200]}"
        )

        # Add outcome info if available
        workflow = content.get("workflow_state", {})
        if outcome := workflow.get("last_result", {}).get("content"):
            lesson += f"\n  Outcome: {outcome[:150]}..."

        lessons.append(lesson)

    return lessons


def _format_recall_results(
    history: list[dict[str, Any]],
    source: str,
) -> dict[str, Any]:
    """
    Fallback formatter when embedding search is unavailable.

    Args:
        history: List of checkpoint states
        source: Source description (e.g., "history_fallback")

    Returns:
        Formatted recall result dict
    """
    lessons = []
    for i, state in enumerate(history[:3]):
        plan = state.get("current_plan", "Unknown")
        lessons.append(f"[Recent #{i + 1}]: {plan[:200]}")

    return {
        "workflow_state": {
            "recalled_lessons": lessons,
            "recalled_experiences": history[:3],
        }
    }


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    from omni.langgraph.checkpoint.lance import LanceCheckpointer
    import tempfile

    async def test_recall_node():
        """Test the recall node with a mock checkpointer."""
        # Create a real checkpointer with test data
        with tempfile.TemporaryDirectory() as tmpdir:
            cp = LanceCheckpointer(uri=f"{tmpdir}/test.lance")

            # Add some test checkpoints
            for i, (plan, vec) in enumerate(
                [
                    ("Fixed authentication bug by adding JWT validation", [0.1, 0.2, 0.3]),
                    ("Database connection pooling issue resolved", [0.9, 0.8, 0.7]),
                ]
            ):
                state = {"current_plan": plan, "step": i, "result": f"Success {i}"}
                cp.put(f"session-{i}", state, metadata={"success": True})

            # Test recall
            result = await recall_node(
                state={"current_plan": "Fix login bug", "workflow_state": {}},
                checkpointer=cp,
                top_k=2,
            )

            print("Recall result:")
            print(json.dumps(result, indent=2, default=str))

            # Verify
            assert "recalled_lessons" in result
            assert len(result["recalled_lessons"]) > 0
            print("\nTest passed!")

    # Run test
    asyncio.run(test_recall_node())
