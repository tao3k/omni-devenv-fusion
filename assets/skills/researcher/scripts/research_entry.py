"""
research_entry.py - Entry point for LangGraph Deep Research Workflow

This module exposes the research workflow as a @skill_command for the MCP server.
"""

from __future__ import annotations

from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger

from research_graph import run_research_workflow

logger = get_logger("researcher.entry")


@skill_command(
    name="run_research_graph",
    description="""
    [CORE] Execute the Deep Research LangGraph workflow.

    This uses LLM reasoning to map, select, and analyze the repo intelligently.

    Workflow:
    1. Clone repository to sandbox
    2. Map file structure (god view)
    3. Scout: LLM decides what to read based on architecture analysis
    4. Digest: Compress selected code into LLM-friendly format
    5. Synthesize: Generate deep analysis report comparing with Omni-Dev patterns
    6. Save report to harvested knowledge base

    Args:
        repo_url: Git repository URL to analyze
        request: Specific analysis goal (default: "Analyze architecture")

    Returns:
        Research report with architecture analysis
    """,
)
async def run_research_graph(
    repo_url: str,
    request: str = "Analyze the architecture",
) -> dict[str, Any]:
    """
    Execute the LangGraph-driven Deep Research workflow.

    Args:
        repo_url: Git repository URL to analyze
        request: Specific analysis goal

    Returns:
        dict with research results and report path
    """
    logger.info("Research workflow invoked", repo_url=repo_url, request=request)

    try:
        result = await run_research_workflow(
            repo_url=repo_url,
            request=request,
            thread_id=f"research-{hash(repo_url) % 10000}",
        )

        # Format the result for the agent
        error = result.get("error")
        if error:
            return {
                "success": False,
                "error": error,
                "steps": result.get("steps", 0),
            }

        final_report = result.get("final_report", "")
        report_path = ""

        # Extract report path from messages if available
        messages = result.get("messages", [])
        if messages:
            content = messages[0].get("content", "") if messages else ""
            # Try to extract path from content
            if "Report saved to:" in content:
                import re

                match = re.search(r"Report saved to: (.+)", content)
                if match:
                    report_path = match.group(1).strip()

        return {
            "success": True,
            "report_preview": final_report[:500] + "..." if final_report else "",
            "report_length": len(final_report) if final_report else 0,
            "report_path": report_path,
            "steps": result.get("steps", 0),
            "selected_targets": result.get("selected_targets", []),
        }

    except Exception as e:
        logger.error("Research workflow failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
        }


__all__ = ["run_research_graph"]
