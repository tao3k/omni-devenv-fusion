# src/agent/capabilities/harvester.py
"""
The Harvester - Distills wisdom from experience.

Phase 12: The Cycle of Evolution

This module implements the "learning" loop of the Agentic OS:
1. Observe: Read session context (SCRATCHPAD.md)
2. Distill: Use PydanticAI to extract key insights
3. Crystallize: Generate standardized Markdown knowledge cards
4. Ingest: Store in ChromaDB vector database

Usage (as MCP tools):
    from agent.capabilities.harvester import register_harvester_tools
    mcp = FastMCP(...)
    register_harvester_tools(mcp)

Usage (as standalone functions):
    from agent.capabilities.harvester import harvest_session_insight
    result = await harvest_session_insight(context_summary="...", files_changed=[...])
"""

import datetime
import json
import os
from pathlib import Path
from typing import List, Optional

import structlog

from agent.core.schema import HarvestedInsight, KnowledgeCategory
from common.mcp_core.gitops import get_project_root
from common.mcp_core.api_key import get_anthropic_api_key
from agent.core.vector_store import get_vector_memory

logger = structlog.get_logger(__name__)


# =============================================================================
# Core Harvester Functions (can be used standalone)
# =============================================================================


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

    # Step 1: AI Reflection & Distillation
    insight = None
    try:
        from anthropic import Anthropic

        # Get API key and base_url from unified source
        api_key = get_anthropic_api_key()
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found. Please configure it in:\n"
                "1. Environment variable: export ANTHROPIC_API_KEY=sk-...\n"
                "2. .claude/settings.json (path from agent/settings.yaml)\n"
                "3. .mcp.json: mcpServers.orchestrator.env.ANTHROPIC_API_KEY"
            )

        # Get base_url from environment (supports MiniMax compatible endpoint)
        base_url = os.environ.get("ANTHROPIC_BASE_URL")

        # Create Anthropic client
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

        # Extract text from response
        response_text = ""
        for block in message.content:
            if hasattr(block, "text") and block.text:
                response_text += block.text

        # Parse JSON response
        import re

        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if json_match:
            import json as json_module

            result_data = json_module.loads(json_match.group())
        else:
            # Try to parse the whole response
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
        # Fallback if pydantic_ai not available
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
        project_root = get_project_root()
        harvest_dir = project_root / "agent" / "knowledge" / "harvested"
        harvest_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename: YYYYMMDD-category-title.md
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        safe_title = "".join(
            c if c.isalnum() or c in "-_ " else "-" for c in insight.title.lower()
        )[:30].strip("-")
        filename = f"{date_str}-{insight.category.value}-{safe_title}.md"
        file_path = harvest_dir / filename

        # Build markdown content
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

        # Write to file
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

    # Return confirmation
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
        project_root = get_project_root()
        harvest_dir = project_root / "agent" / "knowledge" / "harvested"

        if not harvest_dir.exists():
            return "📭 No harvested knowledge yet."

        files = sorted(harvest_dir.glob("*.md"))

        if not files:
            return "📭 No harvested knowledge yet."

        lines = ["# 🌾 Harvested Knowledge", ""]

        for fpath in files:
            # Extract metadata from filename
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
        project_root = get_project_root()
        scratchpad = project_root / ".memory" / "active_context" / "SCRATCHPAD.md"

        if not scratchpad.exists():
            return "No SCRATCHPAD.md found."

        content = scratchpad.read_text(encoding="utf-8")

        # Return first 2000 chars as summary
        if len(content) > 2000:
            return content[:2000] + "\n... (truncated)"

        return content

    except Exception as e:
        return f"❌ Failed to read SCRATCHPAD.md: {e}"


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_harvester_tools(mcp) -> None:
    """Register all harvester tools with the MCP server."""

    @mcp.tool(name="harvest_session_insight")
    async def harvest_session_insight_tool(
        context_summary: str,
        files_changed: Optional[List[str]] = None,
    ) -> str:
        """[Evolution] Call this AFTER completing a complex task."""
        return await harvest_session_insight(context_summary, files_changed)

    @mcp.tool(name="list_harvested_knowledge")
    async def list_harvested_knowledge_tool() -> str:
        """List all harvested knowledge entries."""
        return list_harvested_knowledge()

    @mcp.tool(name="get_scratchpad_summary")
    async def get_scratchpad_summary_tool() -> str:
        """Get a summary of the current session context from SCRATCHPAD.md."""
        return get_scratchpad_summary()

    logger.info("Harvester tools registered")


__all__ = [
    "register_harvester_tools",
    "harvest_session_insight",
    "list_harvested_knowledge",
    "get_scratchpad_summary",
]
