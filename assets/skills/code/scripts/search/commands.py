"""
Command exports for search subpackage.

This file is loaded by the skill framework to discover @skill_command decorated functions.
"""

from typing import Any

from omni.foundation.api.decorators import skill_command
from .graph import execute_search


__all__ = ["code_search"]


@skill_command(
    name="code_search",
    category="search",
    description="""
    Interactive Code Search - The primary search tool.

    Automatically routes queries to the best engine:
    - AST (Structural): 'class User', 'def authenticate'
    - Vector (Semantic): 'how does auth work?', 'user validation logic'
    - Grep (Exact): 'TODO', 'FIXME', '"error message"'

    Returns structured XML optimized for LLM consumption.

    Args:
        - query: Search query (required)
        - session_id: Optional session ID for tracking

    Returns:
        XML-formatted search results with interactive guidance.
    """,
)
async def code_search(query: str, session_id: str = "default") -> str:
    """Execute interactive code search.

    Uses LangGraph to orchestrate parallel search execution
    and returns XML-formatted results.
    """
    try:
        result = await execute_search(query, session_id)
        return result.get("final_output", "")
    except Exception as e:
        return f"<error>{str(e)}</error>"
