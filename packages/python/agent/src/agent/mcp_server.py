"""
src/agent/mcp_server.py
Omni MCP Server - Exposes Omni Skills to External Clients.

Phase 19.6 Rev: Omni-Claude Symbiosis
Exposes Omni's capabilities (RAG, Memory, Reviewer) as MCP tools.

This allows Claude Code, Cursor, Windsurf, etc. to:
- Query Omni's vector memory (Phase 16)
- Request code reviews from ReviewerAgent
- Access project-specific knowledge

Usage:
    # Start MCP Server
    python -m agent.mcp_server

    # Configure Claude Code to connect
    # Add to Claude Desktop or VS Code settings
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import Tool as MCPTool
import structlog

from agent.core.context_loader import load_system_context
from agent.core.session import SessionManager
from agent.core.telemetry import CostEstimator

logger = structlog.get_logger()

# Create MCP Server
mcp = FastMCP("omni-agentic-os")

# Global session manager for MCP tools
_session_manager: SessionManager = None


def get_session_manager() -> SessionManager:
    """Get or create session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# =============================================================================
# System Context Resource
# =============================================================================


@mcp.resource("omni://system/active_context")
def get_active_context() -> str:
    """
    Returns the dynamic system prompts and routing rules for all active skills.
    This is the "brain dump" that external clients can read.
    """
    try:
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        return registry.get_combined_context()
    except Exception as e:
        return f"Error loading context: {e}"


# =============================================================================
# Memory/RAG Tools
# =============================================================================


@mcp.tool()
async def omni_search_memory(query: str, n_results: int = 5) -> str:
    """
    Search Omni's long-term memory (Phase 16 RAG).

    Args:
        query: Search query
        n_results: Number of results to return

    Returns:
        Relevant memories from the vector store
    """
    session = get_session_manager()
    session.log("tool", "mcp_client", f"Memory search: {query}")

    try:
        from agent.capabilities.librarian import search_memory

        results = await search_memory(query, n_results=n_results)

        if not results:
            return "No relevant memories found."

        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.get('content', '')[:200]}...")

        session.log(
            "tool",
            "mcp_client",
            f"Memory search returned {len(results)} results",
        )

        return "\n".join(formatted)

    except Exception as e:
        logger.error("Memory search failed", error=str(e))
        return f"Error searching memory: {e}"


@mcp.tool()
async def omni_ingest_knowledge(documents: list, ids: list = None) -> str:
    """
    Ingest documents into Omni's long-term memory.

    Args:
        documents: List of document texts to ingest
        ids: Optional list of IDs (auto-generated if not provided)

    Returns:
        Ingestion status
    """
    session = get_session_manager()
    session.log("tool", "mcp_client", f"Ingesting {len(documents)} documents")

    try:
        from agent.capabilities.harvester import ingest_knowledge as harvest_ingest

        result = await harvest_ingest(documents=documents, ids=ids or None)

        session.log(
            "tool",
            "mcp_client",
            f"Successfully ingested {len(documents)} documents",
        )

        return f"Successfully ingested {len(documents)} documents."

    except Exception as e:
        logger.error("Knowledge ingestion failed", error=str(e))
        return f"Error ingesting knowledge: {e}"


# =============================================================================
# Reviewer Tools
# =============================================================================


@mcp.tool()
async def omni_request_review(
    code: str,
    language: str = "python",
    focus_areas: list = None,
) -> str:
    """
    Request a code review from Omni's ReviewerAgent.

    Args:
        code: Code to review
        language: Programming language
        focus_areas: Areas to focus on (security, performance, style, etc.)

    Returns:
        Review feedback
    """
    session = get_session_manager()

    try:
        from agent.core.agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent()

        # Create a mock task and context for review
        task = f"Review {language} code"
        context = {
            "constraints": focus_areas or ["security", "correctness", "style"],
        }

        result = await reviewer.audit(task=task, agent_output=code, context=context)

        session.log(
            "tool",
            "mcp_client",
            f"Review completed: approved={result.approved}",
        )

        # Format response
        response = [
            f"## Code Review ({'✅ Approved' if result.approved else '❌ Rejected'})",
            "",
        ]

        if result.feedback:
            response.append(f"**Feedback**: {result.feedback}")

        if result.issues_found:
            response.append("**Issues Found**:")
            for issue in result.issues_found:
                response.append(f"- {issue}")

        if result.suggestions:
            response.append("**Suggestions**:")
            for suggestion in result.suggestions:
                response.append(f"- {suggestion}")

        response.append("")
        response.append(f"Confidence: {result.confidence:.2%}")

        session.log(
            "tool",
            "mcp_client",
            f"Review complete: {len(result.issues_found)} issues",
        )

        return "\n".join(response)

    except Exception as e:
        logger.error("Review failed", error=str(e))
        return f"Error during review: {e}"


# =============================================================================
# Session/Telemetry Tools
# =============================================================================


@mcp.tool()
def omni_get_session_summary() -> str:
    """
    Get the current session summary (Black Box).

    Returns:
        Session ID, cost, and event count
    """
    session = get_session_manager()
    return session.get_summary()


@mcp.tool()
def omni_list_sessions() -> str:
    """
    List all available sessions.

    Returns:
        List of session IDs with event counts
    """
    sessions = SessionManager.list_sessions()

    if not sessions:
        return "No sessions found."

    formatted = ["Available Sessions:", ""]
    for s in sessions:
        formatted.append(f"- {s['session_id']} ({s['events']} events)")

    return "\n".join(formatted)


# =============================================================================
# Context Generation Tools
# =============================================================================


@mcp.tool()
def omni_generate_context(
    mission: str,
    relevant_files: list = None,
) -> str:
    """
    Generate dynamic context file for Claude Code.

    This creates a CLAUDE.md-style context that can be passed to Claude CLI.

    Args:
        mission: Mission brief
        relevant_files: Files relevant to the mission

    Returns:
        Generated context content
    """
    from agent.core.adapters.claude_cli import ContextInjector

    injector = ContextInjector()
    context = injector.generate_context_file(
        mission_brief=mission,
        relevant_files=relevant_files or [],
    )

    session = get_session_manager()
    session.log(
        "tool",
        "mcp_client",
        f"Context generated for mission: {mission[:50]}...",
    )

    return context


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the Omni MCP Server."""
    import argparse

    parser = argparse.ArgumentParser(description="Omni Agentic OS - MCP Server")
    parser.add_argument("--port", type=int, default=None, help="Port to run on")
    parser.add_argument("--stdio", action="store_true", default=True, help="Use stdio transport")
    args = parser.parse_args()

    # Load system context
    system_prompt = load_system_context()

    logger.info("🚀 Starting Omni MCP Server")
    logger.info("📦 Available tools:")
    for tool in mcp._tool_manager._tools.values():
        logger.info(f"  - {tool.name}")

    if args.stdio:
        # Run with stdio transport (for Claude Desktop)
        mcp.run(transport="stdio")
    else:
        # Run with HTTP transport
        mcp.run(host="0.0.0.0", port=args.port or 3000)


if __name__ == "__main__":
    main()
