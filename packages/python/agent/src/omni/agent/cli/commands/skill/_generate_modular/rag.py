"""
rag.py - RAG Retrieval for Skill Generation

Provides semantic search using SkillIndexer to find similar skills
as few-shot examples for LLM-based code generation.
"""

from __future__ import annotations

from typing import Any

from omni.core.router.indexer import SkillIndexer
from omni.foundation.bridge import SearchResult
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.cli.generate.rag")


async def retrieve_similar_skills(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieve similar skills from the Cortex using RAG.

    Uses SkillIndexer to find the most similar existing skills,
    returning their content as few-shot examples for the LLM.

    Args:
        query: Natural language description of the new skill
        limit: Maximum number of examples to retrieve

    Returns:
        List of example dicts with skill_name, command_name, content, score
    """
    try:
        indexer = SkillIndexer()
        indexer.initialize()

        if not indexer.is_ready:
            logger.warning("Cortex not available, skipping RAG")
            return []

        # Search for similar skills
        results: list[SearchResult] = await indexer.search(query, limit=limit * 2)

        if not results:
            logger.debug("No similar skills found in Cortex")
            return []

        # Format results as examples
        examples: list[dict[str, Any]] = []
        seen_skills = set()

        for r in results[:limit]:
            skill_name = r.payload.get("skill_name", "unknown") if r.payload else "unknown"
            cmd_name = r.payload.get("command", "") if r.payload else ""

            # Avoid duplicates
            key = f"{skill_name}:{cmd_name}"
            if key in seen_skills:
                continue
            seen_skills.add(key)

            example = {
                "skill_name": skill_name,
                "command_name": cmd_name,
                "content": r.content,
                "score": r.score,
            }
            examples.append(example)

        logger.info(f"Retrieved {len(examples)} RAG examples for: {query[:50]}...")
        return examples

    except ImportError as e:
        logger.warning(f"RAG unavailable (missing dependency): {e}")
        return []
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return []


def format_rag_context(examples: list[dict[str, Any]]) -> str:
    """Format RAG examples into a prompt-friendly string.

    Args:
        examples: List of example dicts from retrieve_similar_skills

    Returns:
        Formatted string for LLM prompt
    """
    if not examples:
        return "No similar skills found in the codebase."

    context_parts = ["Reference implementations (learn patterns, do NOT copy):\n"]

    for ex in examples:
        skill = ex["skill_name"]
        cmd = ex["command_name"]
        content = ex["content"]
        score = ex["score"]

        context_parts.append(f"--- {skill}/{cmd} (relevance: {score:.2f}) ---")
        context_parts.append(content)
        context_parts.append("")

    return "\n".join(context_parts)


__all__ = ["retrieve_similar_skills", "format_rag_context"]
