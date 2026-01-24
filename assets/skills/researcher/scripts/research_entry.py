"""
research_entry.py - Entry point for Sharded Deep Research Workflow

Uses unified Rust LanceDB CheckpointStore for persistent state:
- State persists across skill reloads
- Supports workflow_id-based retrieval

This module exposes the research workflow as a @skill_command for the MCP server.
Only one entry point: run_research_graph
"""

from __future__ import annotations

from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger

from .research_graph import _WORKFLOW_TYPE, run_research_workflow

logger = get_logger("researcher.entry")


def _get_workflow_id(repo_url: str) -> str:
    """Generate consistent workflow_id from repo_url."""
    return f"research-{hash(repo_url) % 10000}"


@skill_command(
    name="run_research_graph",
    description="""
    Execute the Sharded Deep Research Workflow.

    This autonomously analyzes large repositories using a Map-Plan-Loop-Synthesize pattern:

    1. **Setup**: Clone repository and generate file tree map
    2. **Architect (Plan)**: LLM breaks down the repo into 3-5 logical shards (subsystems)
    3. **Process Shard (Loop)**: For each shard - compress with repomix + analyze with LLM
    4. **Synthesize**: Generate index.md linking all shard analyses

    This approach handles large codebases that exceed LLM context limits by analyzing
    one subsystem at a time, then combining results.

    Args:
        - repo_url: str - Git repository URL to analyze (required)
        - request: str = "Analyze the architecture" - Specific analysis goal

    Returns:
        dict with success status, harvest directory path, and shard summaries
    """,
    # MCP Annotations for LLM context
    category="research",
    read_only=False,
    destructive=False,
    idempotent=True,
    open_world=True,
)
async def run_research_graph(
    repo_url: str,
    request: str = "Analyze the architecture",
) -> dict[str, Any]:
    """
    Execute the Sharded Deep Research workflow.

    This is a Blocking Call. During await, the LLM cannot receive new User Input
    or call other Tools. This naturally implements "Workflow Exclusive".

    Args:
        - repo_url: str - Git repository URL to analyze
        - request: str - Specific analysis goal

    Returns:
        dict with success status, report path, and research results
    """
    logger.info("Sharded research workflow invoked", repo_url=repo_url, request=request)

    # Generate workflow_id for checkpoint tracking
    workflow_id = _get_workflow_id(repo_url)

    # Here is a "Blocking Call".
    # During await, the LLM cannot receive new User Input or call other Tools.
    # This naturally implements "Workflow Exclusive".
    print(f"🔒 [MCP] Locking context for Research Workflow: {repo_url} (id: {workflow_id})")

    try:
        result = await run_research_workflow(
            repo_url=repo_url,
            request=request,
        )

        print("🔓 [MCP] Workflow complete. Releasing lock.")

        error = result.get("error")
        if error:
            return {
                "success": False,
                "error": error,
                "steps": result.get("steps", 0),
                "workflow_id": workflow_id,
                "workflow_type": _WORKFLOW_TYPE,
            }

        # Extract harvest directory from messages
        harvest_dir = result.get("harvest_dir", "")
        shard_analyses = result.get("shard_analyses", [])

        # Format summary from messages
        messages = result.get("messages", [])
        summary = ""
        if messages:
            summary = messages[0].get("content", "")

        return {
            "success": True,
            "harvest_dir": harvest_dir,
            "shards_analyzed": len(shard_analyses),
            "shard_summaries": shard_analyses,
            "summary": summary,
            "steps": result.get("steps", 0),
            "workflow_id": workflow_id,
            "workflow_type": _WORKFLOW_TYPE,
        }

    except Exception as e:
        print("🔓 [MCP] Workflow failed. Releasing lock.")
        logger.error("Research workflow failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "workflow_id": workflow_id,
            "workflow_type": _WORKFLOW_TYPE,
        }


__all__ = ["run_research_graph"]
