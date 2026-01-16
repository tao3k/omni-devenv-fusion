# capabilities/learning/harvester.py
"""
The Harvester - Distills wisdom from experience.

Phase 12: The Cycle of Evolution

This module implements the "learning" loop of the Agentic OS:
1. Observe: Read session context (SCRATCHPAD.md)
2. Distill: Use LLM to extract key insights
3. Crystallize: Generate standardized Markdown knowledge cards
4. Ingest: Store in vector database

Phase 32: Modularized from harvester.py

Usage (as standalone functions):
    from agent.capabilities.learning.harvester import harvest_session_insight
    result = await harvest_session_insight(context_summary="...", files_changed=[...])
"""

import datetime
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import structlog

from agent.core.schema import HarvestedInsight, KnowledgeCategory
from common.mcp_core.api.api_key import get_anthropic_api_key
from agent.core.vector_store import get_vector_memory

logger = structlog.get_logger(__name__)


# =============================================================================
# Phase 39: Routing Feedback Store (Self-Evolving Loop)
# =============================================================================

# Feedback storage uses CACHE_DIR from common.cache_path
# Path: {project_root}/{cache_dir}/memory/routing_feedback.json


class FeedbackStore:
    """
    [Phase 39] Lightweight store for routing reinforcement learning.
    [Phase 40] With time-based decay mechanism.

    Maps (normalized_query, skill_id) -> score (weight adjustment).
    Positive scores boost future routing, negative scores penalize.

    Storage: JSON file for simplicity (can migrate to ChromaDB later).

    Decay Mechanism (Phase 40):
    - Scores decay by 1% each time they are read
    - This prevents "Matthew effect" (old successful skills dominating forever)
    - Gives new skills a fair chance to prove themselves
    """

    # Score bounds to prevent runaway accumulation
    MIN_SCORE = -0.3  # Maximum penalty
    MAX_SCORE = 0.3  # Maximum boost
    DECAY_FACTOR = 0.1  # How much each feedback affects score
    TIME_DECAY_RATE = 0.99  # [Phase 40] Decay multiplier per read (1% decay)

    def __init__(self):
        self._data: Dict[str, Dict[str, float]] = {}
        self._db_path: Optional[Path] = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load feedback data."""
        if self._loaded:
            return

        try:
            from common.cache_path import CACHE_DIR

            self._db_path = CACHE_DIR("memory", "routing_feedback.json")

            if self._db_path.exists():
                self._data = json.loads(self._db_path.read_text(encoding="utf-8"))
                logger.debug("Feedback store loaded", entries=len(self._data))
            else:
                self._data = {}
        except Exception as e:
            logger.warning("Failed to load feedback store", error=str(e))
            self._data = {}

        self._loaded = True

    def _save(self) -> None:
        """Persist feedback data to disk."""
        if self._db_path is None:
            return

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Failed to save feedback store", error=str(e))

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query for consistent matching."""
        # Lowercase, collapse whitespace, strip
        return " ".join(query.lower().split())

    def record_feedback(self, query: str, skill_id: str, success: bool) -> float:
        """
        Record user feedback for a routing decision.

        Args:
            query: The user query that was routed
            skill_id: The skill that was selected/executed
            success: True if user accepted/executed, False if rejected

        Returns:
            The new score for this (query, skill) pair
        """
        self._ensure_loaded()

        norm_query = self._normalize_query(query)
        score_delta = self.DECAY_FACTOR if success else -self.DECAY_FACTOR

        if norm_query not in self._data:
            self._data[norm_query] = {}

        current_score = self._data[norm_query].get(skill_id, 0.0)
        new_score = current_score + score_delta

        # Clamp to bounds
        new_score = max(self.MIN_SCORE, min(self.MAX_SCORE, new_score))

        self._data[norm_query][skill_id] = new_score
        self._save()

        logger.info(
            "Routing feedback recorded",
            query=norm_query[:50],
            skill=skill_id,
            success=success,
            old_score=round(current_score, 3),
            new_score=round(new_score, 3),
        )

        return new_score

    def get_boost(self, query: str, skill_id: str) -> float:
        """
        Get the learned boost/penalty for a skill given a query.

        [Phase 40] Applies time-based decay on read to prevent stale data
        from dominating decisions forever.

        Args:
            query: The user query
            skill_id: The skill to check

        Returns:
            Score adjustment (-0.3 to +0.3)
        """
        self._ensure_loaded()
        norm_query = self._normalize_query(query)

        if norm_query not in self._data:
            return 0.0

        if skill_id not in self._data[norm_query]:
            return 0.0

        # [Phase 40] Apply decay and update stored value
        current_score = self._data[norm_query][skill_id]

        # Only decay non-zero scores
        if abs(current_score) > 0.01:
            decayed_score = current_score * self.TIME_DECAY_RATE

            # If score becomes negligible, remove it
            if abs(decayed_score) < 0.01:
                del self._data[norm_query][skill_id]
                # Clean up empty query entries
                if not self._data[norm_query]:
                    del self._data[norm_query]
                self._save()
                return 0.0

            # Update with decayed value (lazy persistence)
            self._data[norm_query][skill_id] = decayed_score
            return decayed_score

        return current_score

    def get_all_boosts(self, query: str) -> Dict[str, float]:
        """
        Get all learned boosts for a query.

        Args:
            query: The user query

        Returns:
            Dict mapping skill_id -> score
        """
        self._ensure_loaded()
        norm_query = self._normalize_query(query)
        return self._data.get(norm_query, {}).copy()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the feedback store."""
        self._ensure_loaded()
        total_pairs = sum(len(skills) for skills in self._data.values())
        return {
            "unique_queries": len(self._data),
            "total_feedback_pairs": total_pairs,
        }


# Singleton instance
_feedback_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    """Get the singleton FeedbackStore instance."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store


def record_routing_feedback(query: str, skill_id: str, success: bool) -> float:
    """
    [Phase 39] Public API to record routing outcome.

    Call this when:
    - success=True: User accepted/executed the routed skill
    - success=False: User rejected/overrode the routing

    Args:
        query: The original user query
        skill_id: The skill that was routed to
        success: Whether the routing was accepted

    Returns:
        The new score for this (query, skill) pair
    """
    return get_feedback_store().record_feedback(query, skill_id, success)


def get_feedback_boost(query: str, skill_id: str) -> float:
    """
    [Phase 39] Get dynamic boost for scoring.

    Used by vector.py to adjust skill scores based on past feedback.
    """
    return get_feedback_store().get_boost(query, skill_id)


async def harvest_session_insight(
    context_summary: str,
    files_changed: Optional[List[str]] = None,
) -> str:
    """
    Distill development experience into permanent knowledge.

    This is the core function that:
    1. Uses LLM to distill wisdom from context
    2. Creates a markdown knowledge card
    3. Ingests into vector database

    Args:
        context_summary: Summary of what was done
        files_changed: List of files modified

    Returns:
        Confirmation message with harvest details
    """
    logger.info("🌾 Harvesting insights from session...")

    if files_changed is None:
        files_changed = []

    insight = None
    content = ""

    # Step 1: AI Reflection & Distillation
    try:
        from anthropic import Anthropic

        api_key = get_anthropic_api_key()
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found. Please configure it in:\n"
                "1. Environment variable: export ANTHROPIC_API_KEY=sk-...\n"
                "2. .claude/settings.json (path from agent/settings.yaml)\n"
                "3. .mcp.json: mcpServers.orchestrator.env.ANTHROPIC_API_KEY"
            )

        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        client = Anthropic(api_key=api_key, base_url=base_url)

        prompt = f"""
        You are a senior software architect specializing in project retrospectives.
        Your task is to distill chaotic development context into clear, actionable engineering wisdom.

        Task Context:
        {context_summary}

        Files Changed:
        {json.dumps(files_changed, indent=2)}

        Please distill this into a JSON object following this schema:
        {{
            "title": "Concise title for the insight",
            "category": "architecture|debugging|pattern|workflow",
            "context": "Problem background or task description",
            "solution": "The solution that was implemented",
            "key_takeaways": ["lesson 1", "lesson 2", "lesson 3"],
            "code_snippet": "representative code snippet (optional)",
            "related_files": ["file1", "file2"]
        }}

        Focus on:
        1. What was the problem?
        2. What was the solution?
        3. What are the key takeaways for future work?

        Return ONLY valid JSON, no markdown formatting.
        """

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = ""
        for block in message.content:
            if hasattr(block, "text") and block.text:
                response_text += block.text

        import re

        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if json_match:
            import json as json_module

            result_data = json_module.loads(json_match.group())
        else:
            result_data = json.loads(response_text)

        insight = HarvestedInsight(
            title=result_data.get("title", "Untitled Insight"),
            category=KnowledgeCategory(result_data.get("category", "workflow")),
            context=result_data.get("context", context_summary),
            solution=result_data.get("solution", "See context"),
            key_takeaways=result_data.get("key_takeaways", []),
            code_snippet=result_data.get("code_snippet"),
            related_files=result_data.get("related_files", files_changed),
        )

        logger.info(
            "AI distillation complete", title=insight.title, category=insight.category.value
        )

    except ImportError:
        logger.warning("pydantic_ai not available, using mock harvest")
        insight = HarvestedInsight(
            title="Manual Insight",
            category=KnowledgeCategory.DEBUGGING_CASE,
            context=context_summary,
            solution="See session logs",
            key_takeaways=["Review session context for details"],
            code_snippet=None,
            related_files=files_changed,
        )
    except Exception as e:
        return f"❌ Harvesting failed during AI processing: {e}"

    # Step 2: Crystallize to Markdown File
    try:
        from common.mcp_core.reference_library import get_reference_path

        harvest_dir = Path(get_reference_path("harvested_knowledge.dir"))
        harvest_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.datetime.now().strftime("%Y%m%d")
        safe_title = "".join(
            c if c.isalnum() or c in "-_ " else "-" for c in insight.title.lower()
        )[:30].strip("-")
        filename = f"{date_str}-{insight.category.value}-{safe_title}.md"
        file_path = harvest_dir / filename

        content_lines = [
            f"# {insight.title}",
            "",
            f"**Category**: {insight.category.value}",
            f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d')}",
            f"**Harvested**: Automatically from development session",
            "",
            "## Context",
            insight.context,
            "",
            "## Solution",
            insight.solution,
            "",
            "## Key Takeaways",
        ]

        for takeaway in insight.key_takeaways:
            content_lines.append(f"- {takeaway}")

        if insight.code_snippet:
            content_lines.extend(
                [
                    "",
                    "## Pattern / Snippet",
                    f"```{insight.category.value}",
                    insight.code_snippet,
                    "```",
                ]
            )

        if insight.related_files:
            content_lines.extend(
                [
                    "",
                    "## Related Files",
                ]
            )
            for fpath in insight.related_files:
                content_lines.append(f"- `{fpath}`")

        content = "\n".join(content_lines)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"📄 Knowledge crystallized: {filename}")

    except Exception as e:
        return f"❌ Harvesting failed during file generation: {e}"

    # Step 3: Auto-Ingest into Vector Database
    try:
        vm = get_vector_memory()
        await vm.add(
            documents=[content],
            ids=[filename],
            metadatas=[
                {
                    "domain": insight.category.value,
                    "source": str(file_path),
                    "type": "harvested_insight",
                    "title": insight.title,
                }
            ],
        )
        logger.info(f"🧠 Knowledge ingested into Neural Matrix: {filename}")

    except Exception as e:
        logger.warning(f"⚠️ File saved but vector ingestion failed: {e}")

    return (
        f"✅ Insight Harvested Successfully!\n"
        f"\n"
        f"📄 **File**: `{filename}`\n"
        f"📁 **Location**: `agent/knowledge/harvested/`\n"
        f"🏷️ **Category**: `{insight.category.value}`\n"
        f"📝 **Title**: `{insight.title}`\n"
        f"\n"
        f"🧠 The insight is now part of the Neural Matrix and will be\n"
        f"   retrieved when relevant queries are made."
    )


def list_harvested_knowledge() -> str:
    """
    List all harvested knowledge entries.

    Returns:
        List of harvested insight files with their metadata
    """
    try:
        from common.mcp_core.reference_library import get_reference_path

        harvest_dir = Path(get_reference_path("harvested_knowledge.dir"))

        if not harvest_dir.exists():
            return "📭 No harvested knowledge yet."

        files = sorted(harvest_dir.glob("*.md"))

        if not files:
            return "📭 No harvested knowledge yet."

        lines = ["# 🌾 Harvested Knowledge", ""]

        for fpath in files:
            parts = fpath.stem.split("-", 3)
            if len(parts) >= 3:
                date = parts[0]
                category = parts[1]
                title = parts[2] if len(parts) > 2 else "Untitled"
                lines.append(f"- `{date}` **[{category}]** {title}")
            else:
                lines.append(f"- `{fpath.name}`")

        lines.extend(
            [
                "",
                f"Total: {len(files)} harvested insights",
            ]
        )

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Failed to list harvested knowledge: {e}"


def get_scratchpad_summary() -> str:
    """
    Get a summary of the current session context from SCRATCHPAD.md.

    Useful as input to harvest_session_insight after completing a task.
    """
    try:
        from common.cache_path import CACHE_DIR

        scratchpad = CACHE_DIR("memory", "active_context", "SCRATCHPAD.md")

        if not scratchpad.exists():
            return "No SCRATCHPAD.md found."

        content = scratchpad.read_text(encoding="utf-8")

        if len(content) > 2000:
            return content[:2000] + "\n... (truncated)"

        return content

    except Exception as e:
        return f"❌ Failed to read SCRATCHPAD.md: {e}"


# =============================================================================
# One Tool Compatible Functions (exported for @omni routing)
# =============================================================================


async def harvest_session_insight_tool(
    context_summary: str,
    files_changed: Optional[List[str]] = None,
) -> str:
    """[Evolution] Call this AFTER completing a complex task."""
    return await harvest_session_insight(context_summary, files_changed)


async def list_harvested_knowledge_tool() -> str:
    """List all harvested knowledge entries."""
    return list_harvested_knowledge()


async def get_scratchpad_summary_tool() -> str:
    """Get a summary of the current session context from SCRATCHPAD.md."""
    return get_scratchpad_summary()


logger.info("Harvester functions loaded (One Tool compatible)")


__all__ = [
    "harvest_session_insight",
    "list_harvested_knowledge",
    "get_scratchpad_summary",
    # One Tool compatible aliases
    "harvest_session_insight_tool",
    "list_harvested_knowledge_tool",
    "get_scratchpad_summary_tool",
    # Phase 39: Feedback Loop
    "FeedbackStore",
    "get_feedback_store",
    "record_routing_feedback",
    "get_feedback_boost",
]
